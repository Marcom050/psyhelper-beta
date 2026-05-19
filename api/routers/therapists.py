"""Therapist-first REST endpoints with ownership enforcement."""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import account_bundle, parse_body, require_active_therapist, require_same_user_or_owner
from api.exceptions import APIValidationError
from api.schemas.therapists import TherapistClientCreateRequest, TherapistClientResponse
from services import auth_service

router = APIRouter()


def _client_payload(username: str, include_wellness: bool = False) -> dict:
    bundle = account_bundle(username)
    metadata = auth_service.load_user_metadata(username)
    payload = TherapistClientResponse(
        username=username,
        metadata=metadata,
        profile=bundle["profile"],
        wellness=bundle["wellness"] if include_wellness else None,
    ).model_dump()
    if not include_wellness:
        payload.pop("wellness", None)
    return payload


async def list_my_clients(request: Request):
    therapist = require_active_therapist(request)
    return JSONResponse({"clients": auth_service.client_accounts_for(therapist.username)})


async def create_my_client(request: Request):
    therapist = require_active_therapist(request)
    body = await parse_body(request, TherapistClientCreateRequest)
    client_username = auth_service.normalize_username(body.username)
    if not client_username:
        raise APIValidationError("Invalid username")
    if auth_service.user_exists(client_username):
        raise APIValidationError("User already exists")
    profile = dict(body.profile or {})
    display_name = str(profile.get("nome") or profile.get("name") or client_username)
    auth_service.create_client_account(therapist.username, client_username, body.password, display_name)
    if profile:
        bundle = auth_service.load_account_bundle(client_username)
        merged_profile = {**bundle["profile"], **profile, "onboarding_completed": bundle["profile"].get("onboarding_completed", False)}
        auth_service.save_account_bundle(client_username, merged_profile, bundle["messages"], bundle["wellness"])
    return JSONResponse(_client_payload(client_username))


async def get_my_client(request: Request):
    require_active_therapist(request)
    client_username, _therapist = require_same_user_or_owner(request, request.path_params["client_username"])
    return JSONResponse(_client_payload(client_username, include_wellness=True))


router.add_api_route("/therapists/me/clients", list_my_clients, methods=["GET"])
router.add_api_route("/therapists/me/clients", create_my_client, methods=["POST"])
router.add_api_route("/therapists/me/clients/{client_username}", get_my_client, methods=["GET"])
