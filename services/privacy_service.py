from datetime import UTC, datetime

from database.audit_log import audit_log_event

VALID_CONSENT_STATUS = {"accepted", "revoked", "pending"}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def apply_consent(metadata: dict, *, actor: str, scope: str, consent_version: str, privacy_policy_version: str, terms_version: str) -> dict:
    updated = dict(metadata or {})
    updated.update(
        {
            "consent_version": consent_version,
            "privacy_policy_version": privacy_policy_version,
            "terms_version": terms_version,
            "consent_accepted_at": now_iso(),
            "consent_accepted_by": actor,
            "consent_scope": scope,
            "consent_revoked_at": None,
            "consent_status": "accepted",
        }
    )
    return updated


def revoke_consent(metadata: dict, *, actor: str) -> dict:
    updated = dict(metadata or {})
    updated["consent_status"] = "revoked"
    updated["consent_revoked_at"] = now_iso()
    updated["consent_accepted_by"] = actor
    return updated


def has_valid_consent(metadata: dict) -> bool:
    if not isinstance(metadata, dict):
        return False
    return metadata.get("consent_status") == "accepted" and bool(metadata.get("consent_accepted_at"))


def audit_consent_accepted(*, actor: str, target: str, tenant_id: str | None, scope: str):
    audit_log_event(
        "consent_accepted",
        actor_username=actor,
        tenant_id=tenant_id,
        metadata={"target": target, "scope": scope},
    )


def audit_consent_revoked(*, actor: str, target: str, tenant_id: str | None):
    audit_log_event(
        "consent_revoked",
        actor_username=actor,
        tenant_id=tenant_id,
        metadata={"target": target},
        severity="warning",
    )
