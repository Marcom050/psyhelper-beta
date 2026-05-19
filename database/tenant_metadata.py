"""Tenant metadata normalization helpers for PsyHelper SaaS accounts."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

TENANT_OWNER_ROLE = "owner"
TENANT_MEMBER_ROLE = "member"
SUBSCRIPTION_STATUSES = {"trialing", "active", "past_due", "canceled", "inactive", "covered_by_therapist"}
BILLING_STATUSES = {"trialing", "active", "past_due", "canceled"}


def normalize_username(value: Any) -> str:
    if value is None:
        return ""
    normalized = str(value).strip().lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_-]", "", normalized)


def _normalize_iso_or_none(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        return None
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return None
    return value


def normalize_tenant_metadata(metadata: dict[str, Any] | None, username: str | None = None) -> dict[str, Any]:
    """Return metadata with backward-compatible tenant and subscription fields.

    ``tenant_id`` is intentionally derived from existing ``therapist_username``
    for clients and from the therapist username for owners so legacy accounts do
    not need an immediate destructive migration.
    """

    data = dict(metadata or {}) if isinstance(metadata, dict) else {}
    normalized_username = normalize_username(username)
    role = str(data.get("role") or "client").strip().lower()
    if role not in {"therapist", "client", "admin"}:
        role = "client"

    therapist_username = normalize_username(data.get("therapist_username")) or None
    tenant_id = normalize_username(data.get("tenant_id")) or None
    tenant_role = str(data.get("tenant_role") or "").strip().lower() or None

    if role == "therapist":
        tenant_id = tenant_id or normalized_username or therapist_username
        tenant_role = TENANT_OWNER_ROLE
        therapist_username = therapist_username or None
    elif role == "client":
        tenant_id = tenant_id or therapist_username
        therapist_username = therapist_username or tenant_id
        tenant_role = TENANT_MEMBER_ROLE
    else:
        tenant_id = tenant_id or normalized_username or None
        therapist_username = None
        tenant_role = TENANT_OWNER_ROLE

    subscription_status = str(data.get("subscription_status") or "inactive").strip().lower()
    if subscription_status not in SUBSCRIPTION_STATUSES:
        subscription_status = "inactive"

    subscription_plan = str(data.get("subscription_plan") or "").strip().lower() or None
    subscription_started_at = _normalize_iso_or_none(data.get("subscription_started_at"))
    subscription_expires_at = _normalize_iso_or_none(data.get("subscription_expires_at"))
    billing_status = str(data.get("billing_status") or "").strip().lower()
    if billing_status not in BILLING_STATUSES:
        billing_status = "trialing" if subscription_status == "trialing" else subscription_status
    if billing_status not in BILLING_STATUSES:
        billing_status = "canceled" if subscription_status == "inactive" else "active"

    data.update(
        {
            "role": role,
            "therapist_username": therapist_username,
            "tenant_id": tenant_id,
            "tenant_role": tenant_role,
            "subscription_status": subscription_status,
            "subscription_plan": subscription_plan,
            "subscription_started_at": subscription_started_at,
            "subscription_expires_at": subscription_expires_at,
            "billing_status": billing_status,
        }
    )
    return data


def resolve_tenant_id(metadata: dict[str, Any] | None, username: str | None = None) -> str | None:
    return normalize_tenant_metadata(metadata, username=username).get("tenant_id")


def resolve_tenant_owner(metadata: dict[str, Any] | None, username: str | None = None) -> str | None:
    normalized = normalize_tenant_metadata(metadata, username=username)
    if normalized.get("role") == "therapist":
        return normalized.get("tenant_id") or normalize_username(username) or None
    return normalized.get("tenant_id") or normalized.get("therapist_username")
