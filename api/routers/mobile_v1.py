"""Mobile-readiness /v1 API surface with backward compatibility."""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import account_bundle, enforce_subscription_read_access, enforce_subscription_write_access, get_current_active_context, parse_body
from api.schemas.common import success_response
from api.schemas.wellness import MoodEntryRequest
from services import auth_service
from services import data_export_service

router = APIRouter()

def _page(items, limit, offset):
    total=len(items)
    return {"items": items[offset:offset+limit], "limit": limit, "offset": offset, "total": total}

async def me(_request: Request):
    current = get_current_active_context(_request)["auth"]
    return JSONResponse(success_response({"username": current.username, "role": current.role, "metadata": current.metadata}))

async def get_profile(request: Request):
    ctx = get_current_active_context(request); current = ctx["auth"]; enforce_subscription_read_access(current)
    return JSONResponse(success_response({"profile": account_bundle(current.username)["profile"]}))

async def patch_profile(request: Request):
    ctx = get_current_active_context(request); current = ctx["auth"]; enforce_subscription_write_access(current)
    payload = await request.json(); profile_updates = payload.get("profile", {}) if isinstance(payload, dict) else {}
    bundle = account_bundle(current.username); bundle["profile"] = {**bundle["profile"], **profile_updates}
    auth_service.save_account_bundle(current.username, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse(success_response({"profile": bundle["profile"]}))

async def chat_history(request: Request):
    ctx = get_current_active_context(request); current = ctx["auth"]; enforce_subscription_read_access(current); bundle = account_bundle(current.username)
    limit = int(request.query_params.get("limit", 50)); offset = int(request.query_params.get("offset", 0))
    return JSONResponse(success_response(_page(bundle["messages"], limit, offset)))

async def create_chat_message(request: Request):
    ctx = get_current_active_context(request); current = ctx["auth"]; enforce_subscription_write_access(current); payload = await request.json(); content = str(payload.get("content", "")).strip()
    bundle = account_bundle(current.username); bundle["messages"].append({"role": "user", "content": content})
    auth_service.save_account_bundle(current.username, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse(success_response({"ok": True}))


async def export_my_data(request: Request):
    ctx = get_current_active_context(request)
    current = ctx["auth"]
    enforce_subscription_read_access(current)
    tenant_id = current.metadata.get("tenant_id") or current.username
    exported = data_export_service.generate_user_export(actor_username=current.username, subject_username=current.username, tenant_id=tenant_id)
    return JSONResponse(success_response({"export": exported}))

async def list_mood_entries(request: Request):
    ctx = get_current_active_context(request); current = ctx["auth"]; enforce_subscription_read_access(current); bundle = account_bundle(current.username)
    limit = int(request.query_params.get("limit", 50)); offset = int(request.query_params.get("offset", 0)); entries = bundle["wellness"].get("mood_entries", [])
    return JSONResponse(success_response(_page(entries, limit, offset)))

async def create_mood_entry(request: Request):
    ctx = get_current_active_context(request); current = ctx["auth"]; enforce_subscription_write_access(current); body = await parse_body(request, MoodEntryRequest)
    bundle = account_bundle(current.username); entry = body.model_dump(); entry.update(body.model_extra or {})
    bundle["wellness"].setdefault("mood_entries", []).append(entry)
    auth_service.save_account_bundle(current.username, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse(success_response({"mood_entry": entry}))

router.add_api_route("/v1/me", me, methods=["GET"])
router.add_api_route("/v1/me/profile", get_profile, methods=["GET"])
router.add_api_route("/v1/me/profile", patch_profile, methods=["PATCH"])
router.add_api_route("/v1/chat/history", chat_history, methods=["GET"])
router.add_api_route("/v1/chat/messages", create_chat_message, methods=["POST"])
router.add_api_route("/v1/wellness/mood-entries", list_mood_entries, methods=["GET"])
router.add_api_route("/v1/wellness/mood-entries", create_mood_entry, methods=["POST"])

router.add_api_route("/v1/me/export", export_my_data, methods=["GET"])
