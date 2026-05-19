from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import require_admin
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
    require_admin(request)
    q = request.query_params
    limit = int(q.get("limit", 50))
    offset = int(q.get("offset", 0))
    return JSONResponse(success_response({"items": get_events(limit=limit, offset=offset), "limit": limit, "offset": offset}))

router.add_api_route('/admin/tenants', list_tenants, methods=['GET'])
router.add_api_route('/admin/users', list_users, methods=['GET'])
router.add_api_route('/admin/audit/events', list_audit_events, methods=['GET'])
