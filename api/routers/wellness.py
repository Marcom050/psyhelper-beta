"""Wellness routes that preserve the existing wellness JSON schema."""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import account_bundle, enforce_subscription_read_access, enforce_subscription_write_access, enforce_tenant_access, get_current_active_context, parse_body, require_same_user_or_owner
from api.schemas.wellness import JourneyGoalCreateRequest, JourneyGoalResponse, JourneyGoalUpdateRequest, MoodEntryRequest, MoodEntryResponse, WellnessResponse
from api.exceptions import APIValidationError
from services.journey_goal_service import JourneyGoalError, create_patient_goal, materialize_initial_goals, update_goal_by_therapist
from services import auth_service, clinical_data_service


router = APIRouter()


async def get_wellness(request: Request):
    ctx = get_current_active_context(request)
    enforce_tenant_access(request, ctx["auth"])
    enforce_subscription_read_access(ctx["auth"])
    username, _current = require_same_user_or_owner(request, request.path_params["username"])
    bundle = account_bundle(username)
    if materialize_initial_goals(bundle["wellness"], bundle["profile"]):
        auth_service.save_account_bundle(username, bundle["profile"], bundle["messages"], bundle["wellness"])
    response = WellnessResponse(username=username, wellness=bundle["wellness"])
    return JSONResponse(response.model_dump())


async def create_mood_entry(request: Request):
    ctx = get_current_active_context(request)
    enforce_tenant_access(request, ctx["auth"])
    enforce_subscription_write_access(ctx["auth"])
    username, _current = require_same_user_or_owner(request, request.path_params["username"])
    body = await parse_body(request, MoodEntryRequest)
    bundle = account_bundle(username)
    wellness = bundle["wellness"]
    entry = body.model_dump()
    entry.update(body.model_extra or {})
    wellness.setdefault("mood_entries", []).append(entry)
    auth_service.save_account_bundle(username, bundle["profile"], bundle["messages"], wellness)
    owner = auth_service.resolve_tenant_owner(auth_service.load_user_metadata(username), username) or username
    clinical_data_service.create_clinical_record(entity_type="mood_entry", entity_id=str(len(wellness.get("mood_entries", []))), owner_username=owner, subject_username=username, lifecycle_status="active", payload=entry, metadata={"source": "api"})
    clinical_data_service.update_snapshot_for_therapist(owner)
    response = MoodEntryResponse(username=username, mood_entry=entry, wellness=wellness)
    return JSONResponse(response.model_dump())


async def create_journey_goal(request: Request):
    ctx = get_current_active_context(request)
    enforce_tenant_access(request, ctx["auth"])
    enforce_subscription_write_access(ctx["auth"])
    username, current = require_same_user_or_owner(request, request.path_params["username"])
    if current.role != "client" or current.username != username:
        raise APIValidationError("Only the patient can add a personal goal")
    body = await parse_body(request, JourneyGoalCreateRequest)
    bundle = account_bundle(username)
    try:
        goal = create_patient_goal(bundle["wellness"], body.title)
    except JourneyGoalError as exc:
        raise APIValidationError(str(exc)) from exc
    auth_service.save_account_bundle(username, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse(JourneyGoalResponse(username=username, goal=goal, wellness=bundle["wellness"]).model_dump())


async def update_journey_goal(request: Request):
    ctx = get_current_active_context(request)
    enforce_tenant_access(request, ctx["auth"])
    enforce_subscription_write_access(ctx["auth"])
    username, current = require_same_user_or_owner(request, request.path_params["username"])
    body = await parse_body(request, JourneyGoalUpdateRequest)
    bundle = account_bundle(username)
    owner = auth_service.resolve_tenant_owner(auth_service.load_user_metadata(username), username) or ""
    try:
        goal = update_goal_by_therapist(
            bundle["wellness"], request.path_params["goal_id"], achieved=body.achieved,
            note=body.therapist_note, actor_username=current.username, patient_owner=owner, actor_role=current.role,
        )
    except (JourneyGoalError, PermissionError) as exc:
        raise APIValidationError(str(exc)) from exc
    auth_service.save_account_bundle(username, bundle["profile"], bundle["messages"], bundle["wellness"])
    return JSONResponse(JourneyGoalResponse(username=username, goal=goal, wellness=bundle["wellness"]).model_dump())

router.add_api_route("/clients/{username}/wellness", get_wellness, methods=["GET"])
router.add_api_route("/clients/{username}/mood-entries", create_mood_entry, methods=["POST"])
router.add_api_route("/clients/{username}/journey-goals", create_journey_goal, methods=["POST"])
router.add_api_route("/clients/{username}/journey-goals/{goal_id}", update_journey_goal, methods=["PATCH"])
