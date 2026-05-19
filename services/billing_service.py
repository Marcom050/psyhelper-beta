"""Billing domain foundation without external payment-provider coupling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


ALLOWED_STATUSES = {"trialing", "active", "grace_period", "past_due", "canceled"}


@dataclass
class BillingState:
    status: str
    eligible: bool
    reason: str = ""


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def resolve_billing_status(metadata: dict, now: datetime | None = None) -> BillingState:
    now = now or datetime.now(timezone.utc)
    status = str(metadata.get("billing_status") or metadata.get("subscription_status") or "trialing").lower()
    if status not in ALLOWED_STATUSES:
        status = "trialing"

    trial_ends_at = _parse_iso(metadata.get("trial_ends_at"))
    grace_ends_at = _parse_iso(metadata.get("grace_ends_at"))
    subscription_expires_at = _parse_iso(metadata.get("subscription_expires_at"))

    if status == "trialing" and trial_ends_at and now > trial_ends_at:
        return BillingState(status="grace_period", eligible=True, reason="trial_expired")
    if status == "active" and subscription_expires_at and now > subscription_expires_at:
        return BillingState(status="grace_period", eligible=True, reason="subscription_expired")
    if status == "grace_period" and grace_ends_at and now > grace_ends_at:
        return BillingState(status="past_due", eligible=False, reason="grace_period_expired")
    if status in {"past_due", "canceled"}:
        return BillingState(status=status, eligible=False, reason="billing_inactive")
    return BillingState(status=status, eligible=True)


def billing_eligibility_check(metadata: dict, now: datetime | None = None) -> bool:
    return resolve_billing_status(metadata, now=now).eligible
