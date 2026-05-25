from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import account_bundle, get_current_active_context, parse_body
from api.exceptions import AuthenticationError, NotFoundError
from api.schemas.post_consultation_onboarding import (
    PostConsultationBaselineRequest,
    PostConsultationCBTEntryRequest,
    PostConsultationDiaryRequest,
    PostConsultationGoalsRequest,
    PostConsultationNextSessionNoteRequest,
    PostConsultationOnboardingCreateRequest,
    PostConsultationOnboardingResponse,
    PostConsultationSummaryResponse,
)
from services import auth_service
from services.post_consultation_onboarding_service import (
    build_second_session_summary,
    ensure_post_consultation_onboarding,
    progress,
    save_step,
)

router = APIRouter()


def _find_onboarding_and_patient(request: Request, onboarding_id: str) -> tuple[str, dict, dict]:
    ctx = get_current_active_context(request)
    current = ctx["auth"]
    candidates = [current.username]
    if current.role == "therapist":
        candidates = [item.get("username") for item in auth_service.get_clients_for_tenant(current.username)]
    for username in candidates:
        if not username or not auth_service.user_exists(username):
            continue
        bundle = auth_service.load_account_bundle(username)
        for item in bundle.get("wellness", {}).get("post_consultation_onboardings", []):
            if item.get("id") == onboarding_id:
                return username, item, bundle
    raise NotFoundError("Onboarding not found")


def _is_expired(onboarding: dict) -> bool:
    exp = onboarding.get("expires_at")
    if not exp:
        return False
    try:
        expiry = datetime.fromisoformat(str(exp))
    except ValueError:
        return False
    return expiry <= datetime.now(timezone.utc)


def _assert_access(request: Request, patient_id: str) -> None:
    ctx = get_current_active_context(request)
    current = ctx["auth"]
    if current.role == "client":
        if current.username != patient_id:
            raise AuthenticationError("Not authorized for requested user")
        return
    if current.role == "therapist":
        metadata = auth_service.load_user_metadata(patient_id)
        owner = auth_service.resolve_tenant_owner(metadata, patient_id)
        if metadata.get("role") == "client" and owner == current.username:
            return
        raise AuthenticationError("Not authorized for requested tenant resource")
    raise AuthenticationError("Not authorized")


def _response(onboarding: dict) -> dict:
    completed, total = progress(onboarding)
    if _is_expired(onboarding):
        onboarding["status"] = "expired"
    payload = PostConsultationOnboardingResponse(
        onboarding=onboarding,
        status=str(onboarding.get("status") or "active"),
        progress={"completed": completed, "total": total},
        expires_at=onboarding.get("expires_at"),
    )
    return payload.model_dump()


async def create_onboarding(request: Request):
    ctx = get_current_active_context(request)
    if ctx["auth"].role != "therapist":
        raise AuthenticationError("Therapist role required")
    body = await parse_body(request, PostConsultationOnboardingCreateRequest)
    patient_id = auth_service.normalize_username(body.patient_id)
    _assert_access(request, patient_id)
    bundle = account_bundle(patient_id)
    onboarding = ensure_post_consultation_onboarding(bundle["wellness"])
    auth_service.save_account_bundle(patient_id, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse(_response(onboarding))


async def get_onboarding(request: Request):
    patient_id, onboarding, bundle = _find_onboarding_and_patient(request, request.path_params["onboarding_id"])
    _assert_access(request, patient_id)
    return JSONResponse(_response(onboarding))


async def patch_baseline(request: Request):
    patient_id, onboarding, bundle = _find_onboarding_and_patient(request, request.path_params["onboarding_id"])
    _assert_access(request, patient_id)
    if get_current_active_context(request)["auth"].role != "client":
        raise AuthenticationError("Client role required")
    body = await parse_body(request, PostConsultationBaselineRequest)
    save_step(onboarding, "baseline", body.model_dump() | (body.model_extra or {}))
    auth_service.save_account_bundle(patient_id, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse(_response(onboarding))


async def patch_goals(request: Request):
    patient_id, onboarding, bundle = _find_onboarding_and_patient(request, request.path_params["onboarding_id"])
    _assert_access(request, patient_id)
    if get_current_active_context(request)["auth"].role != "client":
        raise AuthenticationError("Client role required")
    body = await parse_body(request, PostConsultationGoalsRequest)
    save_step(onboarding, "goals", body.model_dump() | (body.model_extra or {}))
    auth_service.save_account_bundle(patient_id, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse(_response(onboarding))


async def patch_diary(request: Request):
    patient_id, onboarding, bundle = _find_onboarding_and_patient(request, request.path_params["onboarding_id"])
    _assert_access(request, patient_id)
    if get_current_active_context(request)["auth"].role != "client":
        raise AuthenticationError("Client role required")
    body = await parse_body(request, PostConsultationDiaryRequest)
    payload = body.model_dump() | (body.model_extra or {})
    save_step(onboarding, "diary", payload)
    auth_service.save_account_bundle(patient_id, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse(_response(onboarding))


async def patch_cbt_entry(request: Request):
    patient_id, onboarding, bundle = _find_onboarding_and_patient(request, request.path_params["onboarding_id"])
    _assert_access(request, patient_id)
    if get_current_active_context(request)["auth"].role != "client":
        raise AuthenticationError("Client role required")
    body = await parse_body(request, PostConsultationCBTEntryRequest)
    save_step(onboarding, "cbt", body.model_dump() | (body.model_extra or {}))
    auth_service.save_account_bundle(patient_id, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse(_response(onboarding))


async def patch_next_session_note(request: Request):
    patient_id, onboarding, bundle = _find_onboarding_and_patient(request, request.path_params["onboarding_id"])
    _assert_access(request, patient_id)
    if get_current_active_context(request)["auth"].role != "client":
        raise AuthenticationError("Client role required")
    body = await parse_body(request, PostConsultationNextSessionNoteRequest)
    save_step(onboarding, "next_session_note", body.model_dump() | (body.model_extra or {}))
    auth_service.save_account_bundle(patient_id, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse(_response(onboarding))


async def get_summary(request: Request):
    patient_id, onboarding, bundle = _find_onboarding_and_patient(request, request.path_params["onboarding_id"])
    _assert_access(request, patient_id)
    summary = build_second_session_summary(onboarding)
    auth_service.save_account_bundle(patient_id, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse(PostConsultationSummaryResponse(onboarding_id=onboarding["id"], summary=summary).model_dump())


router.add_api_route("/api/v1/post-consultation-onboarding", create_onboarding, methods=["POST"])
router.add_api_route("/api/v1/post-consultation-onboarding/{onboarding_id}", get_onboarding, methods=["GET"])
router.add_api_route("/api/v1/post-consultation-onboarding/{onboarding_id}/baseline", patch_baseline, methods=["PATCH"])
router.add_api_route("/api/v1/post-consultation-onboarding/{onboarding_id}/goals", patch_goals, methods=["PATCH"])
router.add_api_route("/api/v1/post-consultation-onboarding/{onboarding_id}/diary", patch_diary, methods=["PATCH"])
router.add_api_route("/api/v1/post-consultation-onboarding/{onboarding_id}/cbt-entry", patch_cbt_entry, methods=["PATCH"])
router.add_api_route("/api/v1/post-consultation-onboarding/{onboarding_id}/next-session-note", patch_next_session_note, methods=["PATCH"])
router.add_api_route("/api/v1/post-consultation-onboarding/{onboarding_id}/summary", get_summary, methods=["GET"])
