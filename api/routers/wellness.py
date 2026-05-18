"""Wellness routes that preserve the existing wellness JSON schema."""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import account_bundle, current_username, parse_body
from api.exceptions import AuthenticationError
from api.schemas.wellness import MoodEntryRequest, MoodEntryResponse, WellnessResponse
from services import auth_service


def _assert_can_access(request: Request, username: str) -> str:
    requested = auth_service.normalize_username(username)
    authenticated = current_username(request)
    if requested != authenticated:
        raise AuthenticationError("X-Username must match requested client")
    return requested

router = APIRouter()


async def get_wellness(request: Request):
    username = _assert_can_access(request, request.path_params["username"])
    response = WellnessResponse(username=username, wellness=account_bundle(username)["wellness"])
    return JSONResponse(response.model_dump())


async def create_mood_entry(request: Request):
    username = _assert_can_access(request, request.path_params["username"])
    body = await parse_body(request, MoodEntryRequest)
    bundle = account_bundle(username)
    wellness = bundle["wellness"]
    entry = body.model_dump()
    entry.update(body.model_extra or {})
    wellness.setdefault("mood_entries", []).append(entry)
    auth_service.save_account_bundle(username, bundle["profile"], bundle["messages"], wellness)
    response = MoodEntryResponse(username=username, mood_entry=entry, wellness=wellness)
    return JSONResponse(response.model_dump())

router.add_api_route("/clients/{username}/wellness", get_wellness, methods=["GET"])
router.add_api_route("/clients/{username}/mood-entries", create_mood_entry, methods=["POST"])
