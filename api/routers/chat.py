"""Chat routes that call the existing chat service with explicit context."""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import COPYRIGHT_POLICY, enforce_subscription_write_access, enforce_tenant_access, get_current_active_context, groq_api_key, parse_body, require_same_user_or_owner
from api.exceptions import APIValidationError
from api.schemas.chat import ChatMessageRequest, ChatMessageResponse
from services.chat_service import DEFAULT_SESSION_ID, ChatContext, get_response as get_chat_response


router = APIRouter()


async def create_chat_message(request: Request):
    body = await parse_body(request, ChatMessageRequest)
    ctx = get_current_active_context(request)
    enforce_tenant_access(request, ctx["auth"])
    enforce_subscription_write_access(ctx["auth"])
    username, _current = require_same_user_or_owner(request, body.username)
    api_key = groq_api_key()
    if not api_key:
        raise APIValidationError("GROQ_API_KEY is not configured")

    context = ChatContext(
        profile=body.profile,
        wellness=body.wellness,
        username=username,
        user_input=body.user_input,
    )
    response = get_chat_response(
        context,
        api_key=api_key,
        copyright_policy=COPYRIGHT_POLICY,
        session_id=body.session_id or DEFAULT_SESSION_ID,
    )
    payload = ChatMessageResponse(username=username, content=response.content)
    return JSONResponse(payload.model_dump())

router.add_api_route("/chat/messages", create_chat_message, methods=["POST"])
