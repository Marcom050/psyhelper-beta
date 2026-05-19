"""Therapist-first REST endpoints with ownership enforcement."""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import account_bundle, parse_body, require_active_therapist, require_same_user_or_owner
from api.exceptions import APIValidationError
from api.schemas.therapists import (
    TherapistClientCreateRequest,
    TherapistClientResponse,
    TherapistClientSnapshotResponse,
    TherapistDashboardResponse,
)
from services import auth_service, subscription_service
from services.analytics_service import therapist_overview
from database.audit_log import log_event

router = APIRouter()


def _recent_mood_trends(wellness: dict, limit: int = 10) -> list[dict]:
    mood_entries = wellness.get("mood_entries", []) if isinstance(wellness, dict) else []
    return sorted(
        [entry for entry in mood_entries if isinstance(entry, dict)],
        key=lambda item: item.get("created_at") or item.get("date") or "",
        reverse=True,
    )[:limit]


def _wellness_summary(wellness: dict) -> dict:
    mood_entries = wellness.get("mood_entries", []) if isinstance(wellness, dict) else []
    return {
        "mood_entries_count": len(mood_entries),
        "timeline_events_count": len(wellness.get("timeline_events", [])),
        "latest_mood": _recent_mood_trends(wellness, limit=1)[0] if _recent_mood_trends(wellness, limit=1) else None,
    }


def _homework_summary(wellness: dict) -> dict:
    assignments = wellness.get("homework_assignments", []) if isinstance(wellness, dict) else []
    submissions = wellness.get("homework_submissions", []) if isinstance(wellness, dict) else []
    submitted_ids = {item.get("assignment_id") for item in submissions if isinstance(item, dict)}
    open_assignments = [item for item in assignments if isinstance(item, dict) and item.get("id") not in submitted_ids]
    return {
        "assignments_total": len(assignments),
        "submissions_total": len(submissions),
        "open_assignments": len(open_assignments),
        "latest_submission": sorted(
            [item for item in submissions if isinstance(item, dict)],
            key=lambda item: item.get("submitted_at", ""),
            reverse=True,
        )[:1],
    }


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
    return JSONResponse({"clients": auth_service.get_clients_for_tenant(therapist.username)})


async def my_dashboard(request: Request):
    therapist = require_active_therapist(request)
    clients = auth_service.get_clients_for_tenant(therapist.username)
    tenant_owner = auth_service.get_tenant_owner(therapist.username) or {
        "username": therapist.username,
        "metadata": therapist.metadata,
        "profile": therapist.profile,
    }
    stats = {
        "total_clients": len(clients),
        "active_clients": len(clients),
        "recent_activity": 0,
    }
    payload = TherapistDashboardResponse(
        tenant={
            "tenant_id": auth_service.resolve_tenant_id(tenant_owner.get("metadata"), therapist.username),
            "owner_username": tenant_owner.get("username"),
            "owner_profile": tenant_owner.get("profile", {}),
            "metadata": tenant_owner.get("metadata", {}),
        },
        subscription=subscription_service.subscription_state_for(therapist.username),
        stats=stats,
    )
    return JSONResponse(payload.model_dump())


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


async def get_my_client_snapshot(request: Request):
    require_active_therapist(request)
    client_username, _therapist = require_same_user_or_owner(request, request.path_params["client_username"])
    bundle = account_bundle(client_username)
    metadata = auth_service.load_user_metadata(client_username)
    payload = TherapistClientSnapshotResponse(
        profile=bundle["profile"],
        metadata=metadata,
        wellness_summary=_wellness_summary(bundle["wellness"]),
        homework_summary=_homework_summary(bundle["wellness"]),
        recent_mood_trends=_recent_mood_trends(bundle["wellness"]),
    )
    log_event("therapist_reads_client_snapshot", actor=_therapist.username, payload={"client": client_username})
    return JSONResponse(payload.model_dump())


async def my_stats(request: Request):
    therapist = require_active_therapist(request)
    return JSONResponse({"stats": therapist_overview(therapist.username)})


async def my_activity(request: Request):
    therapist = require_active_therapist(request)
    stats = therapist_overview(therapist.username)
    return JSONResponse({"activity": {"recent_activity_timestamp": stats.get("recent_activity_timestamp"), "active_clients": stats.get("active_clients")}})


async def my_homework_overview(request: Request):
    therapist = require_active_therapist(request)
    stats = therapist_overview(therapist.username)
    return JSONResponse({"homework_overview": {"pending_homework_count": stats.get("pending_homework_count"), "homework_completion_pct": stats.get("homework_completion_pct")}})


async def my_risk_overview(request: Request):
    therapist = require_active_therapist(request)
    stats = therapist_overview(therapist.username)
    return JSONResponse({"risk_overview": {"average_anxiety": stats.get("average_anxiety"), "average_stress": stats.get("average_stress")}})


router.add_api_route("/therapists/me/dashboard", my_dashboard, methods=["GET"])
router.add_api_route("/therapists/me/clients", list_my_clients, methods=["GET"])
router.add_api_route("/therapists/me/clients", create_my_client, methods=["POST"])
router.add_api_route("/therapists/me/clients/{client_username}", get_my_client, methods=["GET"])
router.add_api_route("/therapists/me/clients/{client_username}/snapshot", get_my_client_snapshot, methods=["GET"])
router.add_api_route("/therapists/me/stats", my_stats, methods=["GET"])
router.add_api_route("/therapists/me/activity", my_activity, methods=["GET"])
router.add_api_route("/therapists/me/homework-overview", my_homework_overview, methods=["GET"])
router.add_api_route("/therapists/me/risk-overview", my_risk_overview, methods=["GET"])
