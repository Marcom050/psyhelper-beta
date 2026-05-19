"""Authentication routes for the temporary PsyHelper API boundary."""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import get_current_user, parse_body
from api.exceptions import APIValidationError, AuthenticationError
from api.schemas.auth import AccessTokenResponse, AuthResponse, LoginRequest, RefreshRequest, SignupRequest, UserResponse
from api.security import create_access_token, create_refresh_token, verify_refresh_token
from services import auth_service

router = APIRouter()


async def signup(request: Request):
    body = await parse_body(request, SignupRequest)
    username = auth_service.normalize_username(body.username)
    if not username:
        raise APIValidationError("Invalid username")
    if body.email and not auth_service.is_valid_email(body.email):
        raise APIValidationError("Invalid email")
    if auth_service.user_exists(username):
        raise APIValidationError("User already exists")

    auth_service.create_user(
        username,
        body.password,
        role=body.role,
        therapist_username=body.therapist_username,
        subscription_status=body.subscription_status,
        profile=body.profile,
        email=body.email,
        beta_disclaimer_accepted_at=body.beta_disclaimer_accepted_at,
    )
    bundle = auth_service.load_account_bundle(username)
    metadata = auth_service.load_user_metadata(username)
    response = AuthResponse(username=username, role=metadata.get("role"), metadata=metadata, profile=bundle["profile"])
    return JSONResponse(response.model_dump())


async def login(request: Request):
    body = await parse_body(request, LoginRequest)
    username = auth_service.normalize_username(body.username)
    if not username or not auth_service.verify_password(username, body.password):
        raise AuthenticationError("Invalid credentials")
    bundle = auth_service.load_account_bundle(username)
    metadata = auth_service.load_user_metadata(username)
    response = AuthResponse(
        username=username,
        role=metadata.get("role"),
        metadata=metadata,
        profile=bundle["profile"],
        access_token=create_access_token(username),
        refresh_token=create_refresh_token(username),
    )
    return JSONResponse(response.model_dump())


async def refresh(request: Request):
    body = await parse_body(request, RefreshRequest)
    payload = verify_refresh_token(body.refresh_token)
    username = auth_service.normalize_username(payload.get("sub", ""))
    if not auth_service.user_exists(username):
        raise AuthenticationError("Unknown user")
    response = AccessTokenResponse(access_token=create_access_token(username))
    return JSONResponse(response.model_dump())


async def me(request: Request):
    current = get_current_user(request)
    response = UserResponse(
        username=current.username,
        role=current.role,
        metadata=current.metadata,
        profile=current.profile,
    )
    return JSONResponse(response.model_dump())

router.add_api_route("/auth/signup", signup, methods=["POST"])
router.add_api_route("/auth/login", login, methods=["POST"])
router.add_api_route("/auth/refresh", refresh, methods=["POST"])
router.add_api_route("/me", me, methods=["GET"])
