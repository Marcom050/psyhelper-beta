from __future__ import annotations

from datetime import UTC, datetime

from database.audit_log import log_event
from database.repository_factory import get_clinical_repository
from services import auth_service, data_rights_service
from services.export_redaction import redact_export_payload


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def generate_user_export(*, actor_username: str, subject_username: str, tenant_id: str, request_id: str | None = None) -> dict:
    bundle = auth_service.load_account_bundle(subject_username)
    metadata = auth_service.load_user_metadata(subject_username)
    if (metadata.get("tenant_id") or subject_username) != tenant_id:
        raise ValueError("cross-tenant export denied")

    clinical_records = get_clinical_repository().list_clinical_records(tenant_id=tenant_id, subject_username=subject_username)
    rights_requests = [
        item for item in data_rights_service.list_requests(tenant_id=tenant_id)
        if item.get("subject_username") == subject_username
    ]

    payload = {
        "generated_at": _now_iso(),
        "subject_username": subject_username,
        "tenant_id": tenant_id,
        "account_profile": bundle.get("profile", {}),
        "consent_privacy": {
            "consent_status": metadata.get("consent_status"),
            "consent_version": metadata.get("consent_version"),
            "consent_scope": metadata.get("consent_scope"),
            "consent_accepted_at": metadata.get("consent_accepted_at"),
            "privacy_policy_version": metadata.get("privacy_policy_version"),
            "terms_version": metadata.get("terms_version"),
        },
        "wellness": bundle.get("wellness", {}),
        "homework": {
            "assignments": bundle.get("wellness", {}).get("homework_assignments", []),
            "submissions": bundle.get("wellness", {}).get("homework_submissions", []),
        },
        "chat_messages": bundle.get("messages", []),
        "reports": bundle.get("wellness", {}).get("weekly_reports", []),
        "clinical_records": clinical_records,
        "data_rights_requests": rights_requests,
    }

    safe_payload = redact_export_payload(payload)
    log_event(
        "data_export_generated",
        actor=actor_username,
        payload={"subject_username": subject_username, "tenant_id": tenant_id, "request_id": request_id},
    )
    return safe_payload
