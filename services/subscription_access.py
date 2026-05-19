from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services import auth_service

ACTIVE_READ = {"trialing", "active", "grace_period", "past_due"}
ACTIVE_WRITE = {"trialing", "active", "grace_period"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def resolve_effective_subscription(username: str, repository=None) -> dict[str, Any]:
    metadata = auth_service.load_user_metadata(username, repository=repository)
    owner = auth_service.resolve_tenant_owner(metadata, username)
    owner_metadata = metadata if owner == username else auth_service.load_user_metadata(owner, repository=repository)
    status = str(owner_metadata.get("billing_status") or owner_metadata.get("subscription_status") or "trialing").lower()

    now = _now()
    trial_ends_at = _parse(owner_metadata.get("trial_ends_at") or owner_metadata.get("subscription_expires_at"))
    grace_ends_at = _parse(owner_metadata.get("grace_ends_at"))
    if status == "trialing" and trial_ends_at and now > trial_ends_at:
        status = "grace_period"
    if status == "grace_period" and grace_ends_at and now > grace_ends_at:
        status = "past_due"

    return {
        "tenant_id": auth_service.resolve_tenant_id(owner_metadata, owner),
        "owner_username": owner,
        "status": status,
        "trial_ends_at": owner_metadata.get("trial_ends_at"),
        "grace_ends_at": owner_metadata.get("grace_ends_at"),
        "subscription_plan": owner_metadata.get("subscription_plan", "therapist_monthly_29_90"),
    }


def tenant_access_state(username: str, repository=None) -> dict[str, Any]:
    sub = resolve_effective_subscription(username, repository=repository)
    status = sub["status"]
    return {
        **sub,
        "can_login": True,
        "can_read": status in ACTIVE_READ,
        "can_write": status in ACTIVE_WRITE,
        "limited_mode": status in {"past_due", "grace_period"},
    }


def can_access_clinical_features(username: str, repository=None) -> bool:
    return tenant_access_state(username, repository=repository)["can_read"]


def can_write_clinical_data(username: str, repository=None) -> bool:
    return tenant_access_state(username, repository=repository)["can_write"]
