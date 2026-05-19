from datetime import datetime, timedelta, timezone
from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse
from api.dependencies import get_current_user, parse_body
from api.exceptions import APIValidationError, AuthenticationError
from api.schemas.auth import AccessTokenResponse, AuthResponse, LoginRequest, RefreshRequest, SignupRequest, UserResponse
from api.security import create_access_token, create_refresh_token, verify_refresh_token
from core.settings import SETTINGS
from database.audit_log import audit_log_event
from services import auth_service

router = APIRouter()
_failed={}; _revoked_refresh=set(); _refresh_family={}

def _now(): return datetime.now(timezone.utc)
def _login_limited(username:str)->bool:
    x=_failed.get(username,{"count":0,"lock_until":None,"window_start":_now()})
    if x.get('lock_until') and x['lock_until']>_now(): return True
    return False

def _record_failure(username:str):
    x=_failed.setdefault(username,{"count":0,"lock_until":None,"window_start":_now()})
    if (_now()-x['window_start']).total_seconds()>SETTINGS.login_rate_limit_window_sec: x['count']=0; x['window_start']=_now()
    x['count']+=1
    if x['count']>=SETTINGS.login_rate_limit_attempts: x['lock_until']=_now()+timedelta(seconds=SETTINGS.login_lockout_sec)

def _reset_failures(username:str): _failed.pop(username,None)

async def signup(request: Request):
    body = await parse_body(request, SignupRequest); username = auth_service.normalize_username(body.username)
    if not username: raise APIValidationError("Invalid username")
    if body.email and not auth_service.is_valid_email(body.email): raise APIValidationError("Invalid email")
    if auth_service.user_exists(username): raise APIValidationError("User already exists")
    auth_service.create_user(username, body.password, role=body.role, therapist_username=body.therapist_username, subscription_status=body.subscription_status, profile=body.profile, email=body.email, beta_disclaimer_accepted_at=body.beta_disclaimer_accepted_at)
    bundle = auth_service.load_account_bundle(username); metadata = auth_service.load_user_metadata(username)
    response = AuthResponse(username=username, role=metadata.get("role"), metadata=metadata, profile=bundle["profile"])
    return JSONResponse(response.model_dump())

async def login(request: Request):
    body = await parse_body(request, LoginRequest); username = auth_service.normalize_username(body.username)
    if _login_limited(username): raise AuthenticationError("Account temporarily locked")
    if not username or not auth_service.verify_password(username, body.password):
        _record_failure(username or body.username); audit_log_event("login_failure", actor_username=username or body.username, ip=request.client.host if request.client else None, metadata={"path":"/auth/login"}); raise AuthenticationError("Invalid credentials")
    _reset_failures(username); md=auth_service.load_user_metadata(username)
    if SETTINGS.strict_production_mode and not md.get('tenant_id'): raise AuthenticationError('Missing tenant_id')
    family_id = _refresh_family.get(username)
    if not family_id: family_id = f"fam-{username}"
    _refresh_family[username]=family_id
    refresh_token=create_refresh_token(username, family_id=family_id)
    audit_log_event("login_success", actor_username=username, tenant_id=md.get('tenant_id'), ip=request.client.host if request.client else None, metadata={"path":"/auth/login"})
    bundle = auth_service.load_account_bundle(username)
    response = AuthResponse(username=username, role=md.get("role"), metadata=md, profile=bundle["profile"], access_token=create_access_token(username), refresh_token=refresh_token)
    return JSONResponse(response.model_dump())

async def refresh(request: Request):
    body = await parse_body(request, RefreshRequest)
    if body.refresh_token in _revoked_refresh: raise AuthenticationError('Refresh token revoked')
    payload = verify_refresh_token(body.refresh_token); username = auth_service.normalize_username(payload.get("sub", ""))
    if not auth_service.user_exists(username): raise AuthenticationError("Unknown user")
    _revoked_refresh.add(body.refresh_token)
    new_refresh = create_refresh_token(username, family_id=payload.get('family_id'))
    audit_log_event("token_refresh", actor_username=username, metadata={"path":"/auth/refresh"})
    response = {"access_token": create_access_token(username), "refresh_token": new_refresh, "token_type":"bearer"}
    return JSONResponse(response)

async def logout(request: Request):
    body=await parse_body(request, RefreshRequest); _revoked_refresh.add(body.refresh_token)
    return JSONResponse({"success":True})

async def me(request: Request):
    current = get_current_user(request)
    response = UserResponse(username=current.username, role=current.role, metadata=current.metadata, profile=current.profile)
    return JSONResponse(response.model_dump())

router.add_api_route("/auth/signup", signup, methods=["POST"])
router.add_api_route("/auth/login", login, methods=["POST"])
router.add_api_route("/auth/refresh", refresh, methods=["POST"])
router.add_api_route('/auth/logout', logout, methods=['POST'])
router.add_api_route("/me", me, methods=["GET"])
