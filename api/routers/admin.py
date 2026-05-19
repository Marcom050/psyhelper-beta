from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import enforce_subscription_read_access, enforce_subscription_write_access, get_current_active_context, require_admin
from api.schemas.common import success_response
from database.audit_log import get_events, log_event
from services import auth_service
from services import data_rights_service
from services import privacy_service
from services import data_export_service

router = APIRouter()


def _paginate(items, limit: int, offset: int):
    return items[offset:offset + limit]


def _all_usernames() -> list[str]:
    import os
    from database.filesystem_account_repository import USERS_DIR
    if not os.path.isdir(USERS_DIR):
        return []
    return sorted([u for u in os.listdir(USERS_DIR) if os.path.isdir(os.path.join(USERS_DIR, u))])


async def list_tenants(request: Request):
    admin = require_admin(request)
    q = request.query_params
    limit = int(q.get("limit", 50))
    offset = int(q.get("offset", 0))
    tenants = []
    for u in _all_usernames():
        md = auth_service.load_user_metadata(u)
        if md.get("role") == "therapist":
            tenants.append({"tenant_id": md.get("tenant_id") or u, "owner": u, "status": md.get("subscription_status", "inactive")})
    log_event("admin_list_tenants", actor=admin.username, payload={"limit": limit, "offset": offset})
    return JSONResponse(success_response({"items": _paginate(tenants, limit, offset), "limit": limit, "offset": offset}))


async def list_users(request: Request):
    admin = require_admin(request)
    q = request.query_params
    limit = int(q.get("limit", 50))
    offset = int(q.get("offset", 0))
    users = [{"username": u, "metadata": auth_service.load_user_metadata(u)} for u in _all_usernames()]
    log_event("admin_list_users", actor=admin.username, payload={"limit": limit, "offset": offset})
    return JSONResponse(success_response({"items": _paginate(users, limit, offset), "limit": limit, "offset": offset}))


async def list_audit_events(request: Request):
    admin = require_admin(request)
    enforce_subscription_read_access(admin)
    q = request.query_params
    limit = int(q.get("limit", 50))
    offset = int(q.get("offset", 0))
    return JSONResponse(success_response({"items": get_events(limit=limit, offset=offset), "limit": limit, "offset": offset}))


async def tenant_users(request: Request):
    admin = require_admin(request)
    enforce_subscription_read_access(admin)
    tenant_id = request.path_params["id"]
    return JSONResponse(success_response({"items": auth_service.get_clients_for_tenant(tenant_id)}))


async def tenant_audit(request: Request):
    admin = require_admin(request)
    enforce_subscription_read_access(admin)
    tenant_id = request.path_params["id"]
    events = [e for e in get_events(limit=500, offset=0) if e.get("tenant_id") == tenant_id or e.get("metadata", {}).get("tenant_id") == tenant_id]
    return JSONResponse(success_response({"items": events}))


async def patch_user_role(request: Request):
    admin = get_current_active_context(request)["auth"]
    enforce_subscription_write_access(admin)
    user_id = request.path_params["id"]
    payload = await request.json()
    md = auth_service.load_user_metadata(user_id)
    md["role"] = str(payload.get("role", md.get("role")))
    auth_service.save_user_metadata(user_id, md)
    log_event("admin_patch_user_role", actor=admin.username, payload={"target": user_id, "role": md["role"]})
    return JSONResponse(success_response({"username": user_id, "role": md["role"]}))


async def patch_user_suspend(request: Request):
    admin = get_current_active_context(request)["auth"]
    enforce_subscription_write_access(admin)
    user_id = request.path_params["id"]
    payload = await request.json()
    md = auth_service.load_user_metadata(user_id)
    md["account_status"] = "suspended" if bool(payload.get("suspended", True)) else "active"
    auth_service.save_user_metadata(user_id, md)
    log_event("admin_user_suspend_reactivate", actor=admin.username, payload={"target": user_id, "account_status": md["account_status"]})
    return JSONResponse(success_response({"username": user_id, "account_status": md["account_status"]}))


async def patch_tenant_suspend(request: Request):
    admin = get_current_active_context(request)["auth"]
    enforce_subscription_write_access(admin)
    tenant_id = request.path_params["id"]
    payload = await request.json()
    owner_md = auth_service.load_user_metadata(tenant_id)
    owner_md["subscription_status"] = "suspended" if bool(payload.get("suspended", True)) else "active"
    auth_service.save_user_metadata(tenant_id, owner_md)
    log_event("admin_tenant_suspend_reactivate", actor=admin.username, payload={"tenant_id": tenant_id, "subscription_status": owner_md["subscription_status"]})
    return JSONResponse(success_response({"tenant_id": tenant_id, "subscription_status": owner_md["subscription_status"]}))


async def list_data_rights_requests(request: Request):
    admin = require_admin(request)
    tenant_id = request.query_params.get("tenant_id")
    status = request.query_params.get("status")
    request_type = request.query_params.get("type")
    items = data_rights_service.list_requests(tenant_id=tenant_id, status=status, request_type=request_type)
    log_event("admin_data_rights_list", actor=admin.username, payload={"tenant_id": tenant_id})
    return JSONResponse(success_response({"items": items}))


async def get_data_rights_request(request: Request):
    require_admin(request)
    item = data_rights_service.get_request(request.path_params["request_id"])
    return JSONResponse(success_response(item or {}))


async def update_data_rights_request(request: Request):
    admin = require_admin(request)
    payload = await request.json()
    item = data_rights_service.update_request_status(request.path_params["request_id"], payload.get("status"), payload.get("metadata"))
    if item and item.get("request_type") == "delete":
        md = auth_service.load_user_metadata(item["subject_username"])
        if item.get("status") in {"processing", "completed"}:
            md["deletion_requested"] = True
        elif item.get("status") in {"rejected", "cancelled"}:
            md["deletion_requested"] = False
        auth_service.save_user_metadata(item["subject_username"], md)
    log_event("admin_data_rights_update", actor=admin.username, payload={"request_id": request.path_params["request_id"], "status": payload.get("status")})
    return JSONResponse(success_response(item or {}))


async def export_data_rights_request(request: Request):
    admin = require_admin(request)
    item = data_rights_service.get_request(request.path_params["request_id"])
    if not item:
        return JSONResponse(success_response({}))
    if item.get("status") not in {"processing", "completed"}:
        item = data_rights_service.update_request_status(item["request_id"], "processing")
    exported = data_export_service.generate_user_export(
        actor_username=admin.username,
        subject_username=item["subject_username"],
        tenant_id=item["tenant_id"],
        request_id=item["request_id"],
    )
    item = data_rights_service.update_request_status(item["request_id"], "completed", {"export_generated_at": exported["generated_at"]})
    log_event("admin_data_rights_export", actor=admin.username, payload={"request_id": item["request_id"]})
    return JSONResponse(success_response({"request": item, "export": exported}))


router.add_api_route('/admin/tenants', list_tenants, methods=['GET'])
router.add_api_route('/admin/users', list_users, methods=['GET'])
router.add_api_route('/admin/audit/events', list_audit_events, methods=['GET'])
router.add_api_route('/admin/tenants/{id}/users', tenant_users, methods=['GET'])
router.add_api_route('/admin/tenants/{id}/audit', tenant_audit, methods=['GET'])
router.add_api_route('/admin/users/{id}/role', patch_user_role, methods=['PATCH'])
router.add_api_route('/admin/users/{id}/suspend', patch_user_suspend, methods=['PATCH'])
router.add_api_route('/admin/tenants/{id}/suspend', patch_tenant_suspend, methods=['PATCH'])
router.add_api_route('/admin/data-rights/requests', list_data_rights_requests, methods=['GET'])
router.add_api_route('/admin/data-rights/requests/{request_id}', get_data_rights_request, methods=['GET'])
router.add_api_route('/admin/data-rights/requests/{request_id}', update_data_rights_request, methods=['PATCH'])
router.add_api_route('/admin/data-rights/requests/{request_id}/export', export_data_rights_request, methods=['GET'])
