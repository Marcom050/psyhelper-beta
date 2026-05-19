"""Mobile-readiness /v1 API surface with backward compatibility."""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import account_bundle, get_current_user, parse_body
from api.schemas.wellness import MoodEntryRequest
from services import auth_service

router = APIRouter()


async def me(_request: Request):
    current = get_current_user(_request)
    return JSONResponse({"username": current.username, "role": current.role, "metadata": current.metadata})


async def get_profile(request: Request):
    current = get_current_user(request)
    return JSONResponse({"profile": account_bundle(current.username)["profile"]})


async def patch_profile(request: Request):
    current = get_current_user(request)
    payload = await request.json()
    profile_updates = payload.get("profile", {}) if isinstance(payload, dict) else {}
    bundle = account_bundle(current.username)
    bundle["profile"] = {**bundle["profile"], **profile_updates}
    auth_service.save_account_bundle(current.username, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse({"profile": bundle["profile"]})


async def chat_history(request: Request):
    current = get_current_user(request)
    bundle = account_bundle(current.username)
    limit = int(request.query_params.get("limit", 50))
    offset = int(request.query_params.get("offset", 0))
    return JSONResponse({"items": bundle["messages"][offset : offset + limit], "limit": limit, "offset": offset})


async def create_chat_message(request: Request):
    current = get_current_user(request)
    payload = await request.json()
    content = str(payload.get("content", "")).strip()
    bundle = account_bundle(current.username)
    bundle["messages"].append({"role": "user", "content": content})
    auth_service.save_account_bundle(current.username, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse({"ok": True})


async def list_mood_entries(request: Request):
    current = get_current_user(request)
    bundle = account_bundle(current.username)
    limit = int(request.query_params.get("limit", 50))
    offset = int(request.query_params.get("offset", 0))
    entries = bundle["wellness"].get("mood_entries", [])
    return JSONResponse({"items": entries[offset : offset + limit], "limit": limit, "offset": offset})


async def create_mood_entry(request: Request):
    current = get_current_user(request)
    body = await parse_body(request, MoodEntryRequest)
    bundle = account_bundle(current.username)
    entry = body.model_dump()
    entry.update(body.model_extra or {})
    bundle["wellness"].setdefault("mood_entries", []).append(entry)
    auth_service.save_account_bundle(current.username, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse({"mood_entry": entry})


router.add_api_route("/v1/me", me, methods=["GET"])
router.add_api_route("/v1/me/profile", get_profile, methods=["GET"])
router.add_api_route("/v1/me/profile", patch_profile, methods=["PATCH"])
router.add_api_route("/v1/chat/history", chat_history, methods=["GET"])
router.add_api_route("/v1/chat/messages", create_chat_message, methods=["POST"])
router.add_api_route("/v1/wellness/mood-entries", list_mood_entries, methods=["GET"])
router.add_api_route("/v1/wellness/mood-entries", create_mood_entry, methods=["POST"])
