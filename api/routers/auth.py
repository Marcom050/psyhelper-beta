from datetime import timezone
from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse
from api.dependencies import get_current_user, parse_body
from api.exceptions import APIValidationError, AuthenticationError
from api.schemas.auth import AccessTokenResponse, AuthResponse, LoginRequest, RefreshRequest, SignupRequest, UserResponse
from api.schemas.common import success_response
from api.security import create_access_token, create_refresh_token, verify_refresh_token, decode_token
from core.settings import SETTINGS
from database.audit_log import audit_log_event
from database.auth_security_repository import get_auth_security_repository
from services import auth_service
from services import privacy_service

router = APIRouter()


def _security_repo():
    return get_auth_security_repository()


async def signup(request: Request):
    body = await parse_body(request, SignupRequest); username = auth_service.normalize_username(body.username)
    if not username: raise APIValidationError("Invalid username")
    if body.email and not auth_service.is_valid_email(body.email): raise APIValidationError("Invalid email")
    if auth_service.user_exists(username): raise APIValidationError("User already exists")
    if body.role == 'admin':
        raise APIValidationError('Admin role cannot be created via signup')
    auth_service.create_user(username, body.password, role=body.role, therapist_username=body.therapist_username, subscription_status=body.subscription_status, profile=body.profile, email=body.email, beta_disclaimer_accepted_at=body.beta_disclaimer_accepted_at)
    bundle = auth_service.load_account_bundle(username); metadata = auth_service.load_user_metadata(username)
    if body.role in {"client","therapist"}:
        metadata = privacy_service.apply_consent(metadata, actor=username, scope=f"{body.role}_signup", consent_version=SETTINGS.consent_version, privacy_policy_version=SETTINGS.privacy_policy_version, terms_version=SETTINGS.terms_version)
        auth_service.save_user_metadata(username, metadata)
        privacy_service.audit_consent_accepted(actor=username, target=username, tenant_id=metadata.get("tenant_id"), scope=f"{body.role}_signup")
    response = AuthResponse(username=username, role=metadata.get("role"), metadata=metadata, profile=bundle["profile"])
    return JSONResponse(response.model_dump())


async def login(request: Request):
    body = await parse_body(request, LoginRequest); username = auth_service.normalize_username(body.username)
    security = _security_repo()
    if security.is_locked(username):
        audit_log_event("lockout_denied", actor_username=username, ip=request.client.host if request.client else None, metadata={"path": "/auth/login"}, severity="warning")
        raise AuthenticationError("Account temporarily locked")
    if not username or not auth_service.verify_password(username, body.password):
        security.record_login_failure(username or body.username)
        audit_log_event("login_failure", actor_username=username or body.username, ip=request.client.host if request.client else None, metadata={"path": "/auth/login"}, severity="warning")
        raise AuthenticationError("Invalid credentials")
    security.reset_login_failures(username); md=auth_service.load_user_metadata(username)
    if SETTINGS.strict_production_mode and not md.get('tenant_id'): raise AuthenticationError('Missing tenant_id')
    family_id = security.get_refresh_family(username) or f"fam-{username}"
    security.set_refresh_family(username, family_id)
    refresh_token=create_refresh_token(username, family_id=family_id)
    audit_log_event("login_success", actor_username=username, tenant_id=md.get('tenant_id'), ip=request.client.host if request.client else None, metadata={"path":"/auth/login"})
    bundle = auth_service.load_account_bundle(username)
    response = AuthResponse(username=username, role=md.get("role"), metadata=md, profile=bundle["profile"], access_token=create_access_token(username), refresh_token=refresh_token)
    return JSONResponse(response.model_dump())


async def refresh(request: Request):
    body = await parse_body(request, RefreshRequest)
    security = _security_repo()
    if security.is_token_revoked(body.refresh_token):
        audit_log_event("refresh_reuse_detected", ip=request.client.host if request.client else None, metadata={"path": "/auth/refresh"}, severity="critical")
        raise AuthenticationError('Refresh token revoked')
    payload = verify_refresh_token(body.refresh_token); username = auth_service.normalize_username(payload.get("sub", ""))
    if not auth_service.user_exists(username): raise AuthenticationError("Unknown user")
    if security.get_refresh_family(username) and payload.get("family_id") != security.get_refresh_family(username):
        security.record_login_failure(username)
        audit_log_event("refresh_family_mismatch", actor_username=username, metadata={"path": "/auth/refresh"}, severity="critical")
        raise AuthenticationError("Refresh token family mismatch")
    security.revoke_token(body.refresh_token, int(payload.get("exp", 0)))
    new_refresh = create_refresh_token(username, family_id=payload.get('family_id'))
    audit_log_event("token_refresh", actor_username=username, metadata={"path":"/auth/refresh"})
    response = {"access_token": create_access_token(username), "refresh_token": new_refresh, "token_type":"bearer"}
    return JSONResponse(response)


async def logout(request: Request):
    body=await parse_body(request, RefreshRequest)
    payload = verify_refresh_token(body.refresh_token)
    _security_repo().revoke_token(body.refresh_token, int(payload.get("exp", 0)))
    audit_log_event("logout", actor_username=auth_service.normalize_username(payload.get("sub", "")), metadata={"path": "/auth/logout"})
    return JSONResponse({"success":True})


async def me(request: Request):
    current = get_current_user(request)
    response = UserResponse(username=current.username, role=current.role, metadata=current.metadata, profile=current.profile)
    return JSONResponse(response.model_dump())


async def onboarding_therapist(request: Request):
    body = await parse_body(request, SignupRequest)
    username = auth_service.normalize_username(body.username)
    if auth_service.user_exists(username):
        raise APIValidationError("User already exists")
    auth_service.create_user(username, body.password, role="therapist", subscription_status="trialing", email=body.email, profile=body.profile)
    metadata = auth_service.load_user_metadata(username)
    metadata["trial_days"] = SETTINGS.beta_trial_days
    metadata = privacy_service.apply_consent(metadata, actor=username, scope="therapist_onboarding", consent_version=SETTINGS.consent_version, privacy_policy_version=SETTINGS.privacy_policy_version, terms_version=SETTINGS.terms_version)
    metadata["billing_status"] = "trialing"
    auth_service.save_user_metadata(username, metadata)
    family_id = f"fam-{username}"
    _security_repo().set_refresh_family(username, family_id)
    refresh_token = create_refresh_token(username, family_id=family_id)
    audit_log_event("onboarding_therapist", actor_username=username, tenant_id=metadata.get("tenant_id"), metadata={"path":"/v1/onboarding/therapist"})
    return JSONResponse(success_response({"username": username, "access_token": create_access_token(username), "refresh_token": refresh_token, "metadata": metadata}))
router.add_api_route("/auth/signup", signup, methods=["POST"])
router.add_api_route("/auth/login", login, methods=["POST"])
router.add_api_route("/auth/refresh", refresh, methods=["POST"])
router.add_api_route('/auth/logout', logout, methods=['POST'])
router.add_api_route("/v1/onboarding/therapist", onboarding_therapist, methods=["POST"] )
router.add_api_route("/me", me, methods=["GET"])
