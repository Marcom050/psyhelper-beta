"""Backend-side dependencies and auth/RBAC helpers for the HTTP API."""

from __future__ import annotations

import logging
import os
from typing import Any, Type

from pydantic import BaseModel, ValidationError
from starlette.requests import Request

from api.exceptions import APIValidationError, AuthenticationError, NotFoundError
from api.security import AuthContext, auth_context_for_username, verify_access_token, decode_token
from services import auth_service
from services import subscription_access
from database.audit_log import log_event
from database.auth_security_repository import get_auth_security_repository

logger = logging.getLogger(__name__)


COPYRIGHT_POLICY = os.getenv(
    "PSYHELPER_COPYRIGHT_POLICY",
    "Non fornire testi protetti da copyright non forniti dall'utente; usa sintesi e indicazioni originali.",
)


def groq_api_key() -> str:
    return os.getenv("GROQ_API_KEY", "")


def active_subscription_statuses() -> set[str]:
    configured = os.getenv("ACTIVE_SUBSCRIPTION_STATUSES", "active,trialing")
    return {status.strip().lower() for status in configured.split(",") if status.strip()}


def use_legacy_header_auth() -> bool:
    return os.getenv("USE_LEGACY_HEADER_AUTH", "false").strip().lower() in {"1", "true", "yes", "y", "on"}


def get_current_user(request: Request) -> AuthContext:
    """Validate Bearer auth and return a typed current-user context.

    Temporary X-Username compatibility is available only when
    USE_LEGACY_HEADER_AUTH=true and is disabled by default.
    """

    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        stripped = token.strip()
        payload = verify_access_token(stripped)
        token_payload = decode_token(stripped)
        if get_auth_security_repository().is_token_revoked(stripped):
            raise AuthenticationError("Token revoked")
        if token_payload.get("typ") != "access":
            raise AuthenticationError("Invalid access token")
        return auth_context_for_username(str(payload.get("sub", "")))

    if use_legacy_header_auth():
        username = auth_service.normalize_username(request.headers.get("x-username", ""))
        if username:
            return auth_context_for_username(username)

    raise AuthenticationError("Missing bearer token")


def current_username(request: Request) -> str:
    return get_current_user(request).username


def require_therapist(request: Request) -> AuthContext:
    current = get_current_user(request)
    if current.role != "therapist":
        raise AuthenticationError("Therapist role required")
    return current




def require_admin(request: Request) -> AuthContext:
    current = get_current_user(request)
    if current.role != "admin":
        raise AuthenticationError("Admin role required")
    return current

def require_client(request: Request) -> AuthContext:
    current = get_current_user(request)
    if current.role != "client":
        raise AuthenticationError("Client role required")
    return current


def require_active_therapist(request: Request) -> AuthContext:
    current = require_therapist(request)
    if current.subscription_status.lower() not in active_subscription_statuses():
        raise AuthenticationError("Active therapist subscription required")
    return current


def _is_suspended(metadata: dict[str, Any]) -> bool:
    return str(metadata.get("account_status") or metadata.get("client_status") or "active").lower() in {"suspended", "archived"}


def get_current_active_context(request: Request) -> dict[str, Any]:
    current = get_current_user(request)
    state = subscription_access.tenant_access_state(current.username)
    if _is_suspended(current.metadata):
        raise AuthenticationError("Account suspended")
    context = {
        "auth": current,
        "is_admin": current.role == "admin",
        "is_therapist": current.role == "therapist",
        "is_client": current.role == "client",
        "subscription_state": state["status"],
        "tenant_access_state": state,
    }
    return context


def enforce_tenant_access(request: Request, user: AuthContext) -> None:
    target = request.path_params.get("username") or request.path_params.get("client_username")
    if not target:
        return
    requested = auth_service.normalize_username(target)
    if not requested or not auth_service.user_exists(requested):
        raise NotFoundError("User not found")
    if user.username == requested or user.role == "admin":
        return
    requested_metadata = auth_service.load_user_metadata(requested)
    if user.role == "therapist" and str(requested_metadata.get("role")) == "client":
        owner = auth_service.resolve_tenant_owner(requested_metadata, requested)
        if owner == user.username:
            return
    raise AuthenticationError("Not authorized for requested tenant resource")


def enforce_subscription_read_access(user: AuthContext) -> None:
    state = subscription_access.tenant_access_state(user.username)
    if not state["can_read"] and user.role != "admin":
        raise AuthenticationError("Subscription does not allow read access")


def enforce_subscription_write_access(user: AuthContext) -> None:
    state = subscription_access.tenant_access_state(user.username)
    if not state["can_write"] and user.role != "admin":
        raise AuthenticationError("Subscription does not allow write access")


def require_same_user_or_owner(request: Request, username: str) -> tuple[str, AuthContext]:
    requested = auth_service.normalize_username(username)
    if not requested or not auth_service.user_exists(requested):
        raise NotFoundError("User not found")
    current = get_current_user(request)
    if current.username == requested:
        return requested, current
    if current.role == "therapist":
        requested_metadata = auth_service.load_user_metadata(requested)
        requested_role = requested_metadata.get("role")
        owner = auth_service.resolve_tenant_owner(requested_metadata, requested)
        if requested_role == "client" and owner == current.username:
            return requested, current
    logger.warning("Invalid tenant access attempt actor=%s target=%s", current.username, requested)
    log_event("tenant_access_denied", actor=current.username, payload={"target": requested})
    raise AuthenticationError("Not authorized for requested user")


def account_bundle(username: str) -> dict[str, Any]:
    normalized = auth_service.normalize_username(username)
    if not auth_service.user_exists(normalized):
        raise NotFoundError("User not found")
    return auth_service.load_account_bundle(normalized)


async def parse_body(request: Request, model: Type[BaseModel]) -> BaseModel:
    try:
        payload = await request.json()
    except Exception as exc:
        raise APIValidationError("Invalid JSON body") from exc
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise APIValidationError(str(exc)) from exc
