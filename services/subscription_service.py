"""Subscription and beta-trial business logic for PsyHelper."""

from datetime import UTC, datetime, timedelta
from typing import Any

from core.settings import SETTINGS
from services.auth_service import load_user_metadata, resolve_tenant_owner

BETA_TRIAL_DAYS = SETTINGS.beta_trial_days
ACTIVE_BILLING_STATUSES = {"trialing", "active"}


def parse_iso_datetime(value):
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def normalize_datetime_utc(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = parse_iso_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def trial_expires_at(created_at):
    created_datetime = normalize_datetime_utc(created_at) or datetime.now(UTC)
    return created_datetime + timedelta(days=BETA_TRIAL_DAYS)


def trial_days_remaining(created_at):
    remaining = trial_expires_at(created_at) - datetime.now(UTC)
    return max(0, remaining.days + (1 if remaining.seconds or remaining.microseconds else 0))


def is_trial_expired(metadata):
    if metadata.get("role") != "therapist":
        return False
    if metadata.get("subscription_status", "inactive").lower() != "trialing":
        return False
    expires_at = normalize_datetime_utc(metadata.get("subscription_expires_at")) or trial_expires_at(metadata.get("created_at"))
    return datetime.now(UTC) >= expires_at


def subscription_state_for(username: str, repository=None) -> dict[str, Any]:
    """Return tenant-owned subscription state for a therapist or inherited client."""

    metadata = load_user_metadata(username, repository=repository)
    owner_username = resolve_tenant_owner(metadata, username)
    owner_metadata = metadata
    inherited = False
    if metadata.get("role") == "client" and owner_username:
        owner_metadata = load_user_metadata(owner_username, repository=repository)
        inherited = True

    status = str(owner_metadata.get("subscription_status") or "inactive").lower()
    billing_status = str(owner_metadata.get("billing_status") or status).lower()
    if status == "trialing" and is_trial_expired(owner_metadata):
        billing_status = "past_due"
    return {
        "tenant_id": resolve_tenant_owner(owner_metadata, owner_username) or owner_username,
        "owner_username": owner_username,
        "inherited": inherited,
        "subscription_status": status,
        "subscription_plan": owner_metadata.get("subscription_plan"),
        "subscription_started_at": owner_metadata.get("subscription_started_at"),
        "subscription_expires_at": owner_metadata.get("subscription_expires_at") or (
            trial_expires_at(owner_metadata.get("created_at")).isoformat(timespec="seconds") if status == "trialing" else None
        ),
        "billing_status": billing_status,
        "trial_days_remaining": trial_days_remaining(owner_metadata.get("created_at")) if status == "trialing" else 0,
    }


def is_subscription_active_for(username, active_subscription_statuses, repository=None):
    state = subscription_state_for(username, repository=repository)
    status = state.get("subscription_status", "inactive")
    if status == "trialing":
        return state.get("billing_status") != "past_due"
    return status in active_subscription_statuses and state.get("billing_status") in ACTIVE_BILLING_STATUSES
