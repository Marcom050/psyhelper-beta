"""Structured clinical data foundation (non-breaking).

Keeps current JSON payloads backward compatible while exposing normalized,
tenant-scoped records for lifecycle tracking and analytics queries.
"""

from dataclasses import dataclass
from datetime import datetime, timezone


CLIENT_STATUSES = {"active", "suspended", "archived"}
HOMEWORK_STATUSES = {"assigned", "submitted", "reviewed", "expired"}
CHAT_STATUSES = {"active", "archived"}
REPORT_STATUSES = {"generated", "locked", "archived"}


@dataclass(frozen=True)
class ClinicalRecordMeta:
    id: str
    tenant_id: str
    owner_username: str
    lifecycle_status: str
    created_at: str
    updated_at: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_status(status: str, allowed: set[str], default: str) -> str:
    value = str(status or "").strip().lower()
    return value if value in allowed else default


def clinical_meta(entity_id: str, tenant_id: str, owner_username: str, lifecycle_status: str, allowed_statuses: set[str], default_status: str) -> ClinicalRecordMeta:
    now = _utc_now_iso()
    return ClinicalRecordMeta(
        id=str(entity_id),
        tenant_id=str(tenant_id),
        owner_username=str(owner_username),
        lifecycle_status=_safe_status(lifecycle_status, allowed_statuses, default_status),
        created_at=now,
        updated_at=now,
    )


def normalized_homework_status(assignment: dict, submissions: set[str], today_iso: str | None = None) -> str:
    status = _safe_status(assignment.get("status", ""), HOMEWORK_STATUSES, "assigned")
    if assignment.get("id") in submissions:
        return "submitted" if status == "assigned" else status
    due = str(assignment.get("due_date") or "").strip()
    if due and today_iso and due < today_iso and status == "assigned":
        return "expired"
    return status


def extract_structured_analytics_rows(username: str, tenant_id: str, wellness: dict) -> dict:
    mood_entries = wellness.get("mood_entries", []) if isinstance(wellness, dict) else []
    assignments = wellness.get("homework_assignments", []) if isinstance(wellness, dict) else []
    submissions = wellness.get("homework_submissions", []) if isinstance(wellness, dict) else []

    submitted_ids = {item.get("assignment_id") for item in submissions if isinstance(item, dict)}
    today_iso = datetime.now(timezone.utc).date().isoformat()

    mood_rows = [
        {
            "tenant_id": tenant_id,
            "client_username": username,
            "entry_date": entry.get("data"),
            "ansia": entry.get("ansia"),
            "stress": entry.get("stress"),
            "umore_intensita": entry.get("umore_intensita"),
        }
        for entry in mood_entries
        if isinstance(entry, dict)
    ]

    homework_rows = [
        {
            "tenant_id": tenant_id,
            "client_username": username,
            "assignment_id": a.get("id"),
            "status": normalized_homework_status(a, submitted_ids, today_iso=today_iso),
            "due_date": a.get("due_date"),
            "assigned_at": a.get("assigned_at"),
        }
        for a in assignments
        if isinstance(a, dict)
    ]
    return {"mood_rows": mood_rows, "homework_rows": homework_rows}
