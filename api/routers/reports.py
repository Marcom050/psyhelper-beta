"""Report routes backed by pure reporting services."""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import account_bundle, enforce_subscription_read_access, enforce_tenant_access, get_current_active_context, require_same_user_or_owner
from api.schemas.reports import ClinicalReportResponse, WeeklyRecapResponse
from services import report_service, auth_service, clinical_data_service


def _clinical_payload(report: report_service.ClinicalReport) -> dict:
    payload = report.as_dict()
    payload.pop("scope_df", None)
    payload["sections"] = [
        {"title": section.title, "lines": section.lines}
        for section in payload.get("sections", [])
    ]
    return payload

router = APIRouter()


async def weekly_recap(request: Request):
    ctx = get_current_active_context(request)
    enforce_tenant_access(request, ctx["auth"])
    enforce_subscription_read_access(ctx["auth"])
    username, _current = require_same_user_or_owner(request, request.path_params["username"])
    bundle = account_bundle(username)
    report = report_service.clinical_snapshot(bundle["wellness"], bundle["messages"])
    recap = report_service.weekly_recap(report)
    response = WeeklyRecapResponse(username=username, items=list(recap), text=recap.to_text(bullet_prefix="- "))
    return JSONResponse(response.model_dump())


async def clinical_report(request: Request):
    ctx = get_current_active_context(request)
    enforce_tenant_access(request, ctx["auth"])
    enforce_subscription_read_access(ctx["auth"])
    username, _current = require_same_user_or_owner(request, request.path_params["username"])
    bundle = account_bundle(username)
    report = report_service.clinical_snapshot(bundle["wellness"], bundle["messages"])
    owner = auth_service.resolve_tenant_owner(auth_service.load_user_metadata(username), username) or username
    clinical_data_service.create_clinical_record(entity_type="report", entity_id=f"clinical:{username}", owner_username=owner, subject_username=username, lifecycle_status="generated", payload=_clinical_payload(report), metadata={"source": "api"})
    clinical_data_service.update_snapshot_for_therapist(owner)
    response = ClinicalReportResponse(username=username, report=_clinical_payload(report))
    return JSONResponse(response.model_dump())

router.add_api_route("/clients/{username}/weekly-recap", weekly_recap, methods=["GET"])
router.add_api_route("/clients/{username}/clinical-report", clinical_report, methods=["GET"])
