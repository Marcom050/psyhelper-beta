from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from database.json_storage import atomic_write_json, load_json_file

logger = logging.getLogger(__name__)
AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", os.path.expanduser("~/psyhelper_data/audit_log.json"))


def _load_events() -> list[dict]:
    if not os.path.exists(AUDIT_LOG_PATH):
        os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
        atomic_write_json(AUDIT_LOG_PATH, [])
    data = load_json_file(AUDIT_LOG_PATH)
    if not isinstance(data, list):
        raise RuntimeError("Invalid audit persistence format")
    return data


def _save_events(events: list[dict]) -> None:
    atomic_write_json(AUDIT_LOG_PATH, events)


def audit_log_event(
    event_type: str,
    actor_username: str | None = None,
    target_username: str | None = None,
    tenant_id: str | None = None,
    ip: str | None = None,
    metadata: dict | None = None,
    severity: str = "info",
) -> str:
    event = {
        "event_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "actor": actor_username,
        "target": target_username,
        "tenant_id": tenant_id,
        "ip": ip,
        "metadata": metadata or {},
        "severity": severity,
    }
    events = _load_events()
    events.append(event)
    _save_events(events)
    logger.info("audit_event=%s actor=%s target=%s", event_type, actor_username, target_username)
    return event["event_id"]


def log_event(event_type: str, actor: str | None = None, payload: dict | None = None) -> None:
    audit_log_event(event_type=event_type, actor_username=actor, metadata=payload or {})


def get_events(limit: int = 50, offset: int = 0) -> list[dict]:
    events = _load_events()[::-1]
    return events[offset : offset + limit]
