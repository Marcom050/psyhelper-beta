"""Patient Session Bridge persistence endpoints."""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import (
    account_bundle, enforce_subscription_read_access,
    enforce_subscription_write_access, enforce_tenant_access,
    get_current_active_context, parse_body, require_same_user_or_owner,
)
from api.exceptions import APIValidationError
from api.schemas.session_bridge import SessionBridgeRequest, SessionBridgeResponse
from services import auth_service
from services.session_bridge_service import (
    SessionBridgeValidationError, get_session_bridge as read_bridge,
    save_session_bridge as write_bridge,
)


router = APIRouter()


async def get_session_bridge(request: Request):
    ctx = get_current_active_context(request)
    enforce_tenant_access(request, ctx["auth"])
    enforce_subscription_read_access(ctx["auth"])
    username, _current = require_same_user_or_owner(request, request.path_params["username"])
    try:
        bridge = read_bridge(account_bundle(username)["wellness"])
    except SessionBridgeValidationError as exc:
        raise APIValidationError(str(exc)) from exc
    return JSONResponse(SessionBridgeResponse(username=username, session_bridge=bridge).model_dump())


async def put_session_bridge(request: Request):
    ctx = get_current_active_context(request)
    enforce_tenant_access(request, ctx["auth"])
    enforce_subscription_write_access(ctx["auth"])
    username, current = require_same_user_or_owner(request, request.path_params["username"])
    if current.role != "client" or current.username != username:
        raise APIValidationError("Only the patient can modify their Session Bridge")
    body = await parse_body(request, SessionBridgeRequest)
    bundle = account_bundle(username)
    try:
        bridge = write_bridge(bundle["wellness"], body.model_dump())
    except SessionBridgeValidationError as exc:
        raise APIValidationError(str(exc)) from exc
    auth_service.save_account_bundle(username, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse(SessionBridgeResponse(username=username, session_bridge=bridge).model_dump())


router.add_api_route("/clients/{username}/session-bridge", get_session_bridge, methods=["GET"])
router.add_api_route("/clients/{username}/session-bridge", put_session_bridge, methods=["PUT"])
