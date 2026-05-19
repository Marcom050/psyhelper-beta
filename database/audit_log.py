"""Append-only JSON audit log foundation."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", os.path.expanduser("~/psyhelper_data/audit_log.jsonl"))


def log_event(event_type: str, actor: str | None = None, payload: dict | None = None) -> None:
    os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "actor": actor,
        "payload": payload or {},
    }
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    logger.info("audit_event=%s actor=%s", event_type, actor)
