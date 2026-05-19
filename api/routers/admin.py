from fastapi import APIRouter
import os
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import enforce_subscription_read_access, enforce_subscription_write_access, get_current_active_context, require_admin
from api.schemas.common import success_response
from database.audit_log import get_events, log_event
from services import auth_service

router = APIRouter()


def _paginate(items, limit: int, offset: int):
    return items[offset:offset + limit]


async def list_tenants(request: Request):
    admin = require_admin(request)
    q = request.query_params
    limit = int(q.get("limit", 50))
    offset = int(q.get("offset", 0))
    therapists = [u for u in auth_service.client_accounts_for("") if False]
    # fallback lightweight scan via known users in audit events is unavailable; use account repo helper when present
    owners = auth_service.get_clients_for_tenant("__none__") if False else []
    log_event("admin_list_tenants", actor=admin.username, payload={"limit": limit, "offset": offset})
    return JSONResponse(success_response({"items": _paginate(owners, limit, offset), "limit": limit, "offset": offset}))


async def list_users(request: Request):
    admin = require_admin(request)
    q = request.query_params
    limit = int(q.get("limit", 50))
    offset = int(q.get("offset", 0))
    users = []
    log_event("admin_list_users", actor=admin.username, payload={"limit": limit, "offset": offset})
    return JSONResponse(success_response({"items": _paginate(users, limit, offset), "limit": limit, "offset": offset}))


async def list_audit_events(request: Request):
    admin = require_admin(request)
    enforce_subscription_read_access(admin)
    q = request.query_params
    limit = int(q.get("limit", 50))
    offset = int(q.get("offset", 0))
    return JSONResponse(success_response({"items": get_events(limit=limit, offset=offset), "limit": limit, "offset": offset}))


def _all_users() -> list[str]:
    users_dir = os.path.expanduser("~/psyhelper_data/users")
    if not os.path.isdir(users_dir):
        return []
    return sorted([u for u in os.listdir(users_dir) if os.path.isdir(os.path.join(users_dir, u))])


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
    log_event("admin_patch_user_suspend", actor=admin.username, payload={"target": user_id, "account_status": md["account_status"]})
    return JSONResponse(success_response({"username": user_id, "account_status": md["account_status"]}))


async def patch_tenant_suspend(request: Request):
    admin = get_current_active_context(request)["auth"]
    enforce_subscription_write_access(admin)
    tenant_id = request.path_params["id"]
    payload = await request.json()
    owner_md = auth_service.load_user_metadata(tenant_id)
    owner_md["subscription_status"] = "suspended" if bool(payload.get("suspended", True)) else "active"
    auth_service.save_user_metadata(tenant_id, owner_md)
    log_event("admin_patch_tenant_suspend", actor=admin.username, payload={"tenant_id": tenant_id, "subscription_status": owner_md["subscription_status"]})
    return JSONResponse(success_response({"tenant_id": tenant_id, "subscription_status": owner_md["subscription_status"]}))

router.add_api_route('/admin/tenants', list_tenants, methods=['GET'])
router.add_api_route('/admin/users', list_users, methods=['GET'])
router.add_api_route('/admin/audit/events', list_audit_events, methods=['GET'])
router.add_api_route('/admin/tenants/{id}/users', tenant_users, methods=['GET'])
router.add_api_route('/admin/tenants/{id}/audit', tenant_audit, methods=['GET'])
router.add_api_route('/admin/users/{id}/role', patch_user_role, methods=['PATCH'])
router.add_api_route('/admin/users/{id}/suspend', patch_user_suspend, methods=['PATCH'])
router.add_api_route('/admin/tenants/{id}/suspend', patch_tenant_suspend, methods=['PATCH'])
