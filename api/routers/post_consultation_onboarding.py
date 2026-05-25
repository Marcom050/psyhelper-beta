from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import enforce_subscription_read_access, enforce_subscription_write_access, get_current_active_context
from services import post_consultation_onboarding_service as service

router = APIRouter(prefix="/api/v1/post-consultation-onboarding")


async def create_onboarding(request: Request):
    ctx = get_current_active_context(request)
    current = ctx["auth"]
    enforce_subscription_write_access(current)
    if current.role != "therapist":
        raise Exception("Therapist role required")
    payload = await request.json()
    patient_id = payload.get("patient_id", "")
    tenant_id = current.metadata.get("tenant_id") or current.username
    item = service.activate_onboarding(therapist_id=current.username, patient_id=patient_id, tenant_id=tenant_id)
    return JSONResponse(item)


async def get_onboarding(request: Request):
    ctx = get_current_active_context(request)
    current = ctx["auth"]
    enforce_subscription_read_access(current)
    onboarding_id = request.path_params["onboarding_id"]
    patient_id = request.query_params.get("patient_id", current.username)
    onboarding = service.get_onboarding(patient_id, onboarding_id)
    tenant_id = current.metadata.get("tenant_id") or current.username
    if current.role == "therapist":
        service.assert_therapist_access(onboarding, current.username, tenant_id)
    else:
        service.assert_patient_access(onboarding, current.username, tenant_id)
    return JSONResponse(onboarding)


async def _patch_step(request: Request, step: str, field: str):
    ctx = get_current_active_context(request)
    current = ctx["auth"]
    enforce_subscription_write_access(current)
    onboarding_id = request.path_params["onboarding_id"]
    payload = await request.json()
    patient_id = payload.get("patient_id", current.username)
    onboarding = service.get_onboarding(patient_id, onboarding_id)
    tenant_id = current.metadata.get("tenant_id") or current.username
    service.assert_patient_access(onboarding, current.username, tenant_id)
    updated = service.update_step(patient_id, onboarding_id, step, payload[field])
    return JSONResponse(updated)


async def patch_baseline(request: Request):
    return await _patch_step(request, "baseline", "baseline")


async def patch_goals(request: Request):
    return await _patch_step(request, "goals", "goals")


async def patch_diary(request: Request):
    return await _patch_step(request, "diary_entries", "diary_entries")


async def patch_cbt_entry(request: Request):
    return await _patch_step(request, "cbt_entry", "cbt_entry")


async def patch_next_session_note(request: Request):
    return await _patch_step(request, "next_session_note", "next_session_note")


async def get_summary(request: Request):
    ctx = get_current_active_context(request)
    current = ctx["auth"]
    enforce_subscription_read_access(current)
    onboarding_id = request.path_params["onboarding_id"]
    patient_id = request.query_params.get("patient_id", current.username)
    summary = service.build_post_consultation_summary(patient_id, current.username, onboarding_id)
    return JSONResponse(summary)

router.add_api_route("", create_onboarding, methods=["POST"])
router.add_api_route("/{onboarding_id}", get_onboarding, methods=["GET"])
router.add_api_route("/{onboarding_id}/baseline", patch_baseline, methods=["PATCH"])
router.add_api_route("/{onboarding_id}/goals", patch_goals, methods=["PATCH"])
router.add_api_route("/{onboarding_id}/diary", patch_diary, methods=["PATCH"])
router.add_api_route("/{onboarding_id}/cbt-entry", patch_cbt_entry, methods=["PATCH"])
router.add_api_route("/{onboarding_id}/next-session-note", patch_next_session_note, methods=["PATCH"])
router.add_api_route("/{onboarding_id}/summary", get_summary, methods=["GET"])
