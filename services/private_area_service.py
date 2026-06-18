"""Privacy-first helpers for the patient private area.

This module only stores and filters patient-authored notes. It performs no
content analysis and never exposes private or revoked entries through therapist
helpers.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

PRIVATE_AREA_KEY = "private_area_entries"
PRIVATE_AREA_SOURCE = "patient_private_area"
PRIVATE_STATUSES = {"private", "shared", "revoked"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_private_area_schema(wellness: dict[str, Any] | None) -> dict[str, Any]:
    if wellness is None:
        wellness = {}
    entries = wellness.setdefault(PRIVATE_AREA_KEY, [])
    if not isinstance(entries, list):
        wellness[PRIVATE_AREA_KEY] = []
    return wellness


def _entries(wellness: dict[str, Any] | Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(wellness, dict):
        return list((wellness or {}).get(PRIVATE_AREA_KEY, []))
    ensure_private_area_schema(wellness)
    return wellness[PRIVATE_AREA_KEY]


def _normalize_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    status = entry.get("share_status") if entry.get("share_status") in PRIVATE_STATUSES else "private"
    return {
        "id": str(entry.get("id") or uuid4()),
        "created_at": entry.get("created_at") or _now_iso(),
        "updated_at": entry.get("updated_at") or entry.get("created_at") or _now_iso(),
        "title": str(entry.get("title") or "Senza titolo"),
        "content": str(entry.get("content") or ""),
        "share_status": status,
        "shared_at": entry.get("shared_at") if status == "shared" else entry.get("shared_at"),
        "revoked_at": entry.get("revoked_at"),
        "source": entry.get("source") or PRIVATE_AREA_SOURCE,
    }


def list_private_area_entries(wellness: Mapping[str, Any] | None, include_private: bool = False) -> list[dict[str, Any]]:
    entries = [_normalize_entry(entry) for entry in (wellness or {}).get(PRIVATE_AREA_KEY, [])]
    if include_private:
        return entries
    return [entry for entry in entries if entry.get("share_status") == "shared"]


def list_patient_private_entries(wellness: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    return list_private_area_entries(wellness, include_private=True)


def list_shared_entries_for_therapist(wellness: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    return list_private_area_entries(wellness, include_private=False)


def create_private_entry(wellness: dict[str, Any], title: str, content: str) -> dict[str, Any]:
    ensure_private_area_schema(wellness)
    now = _now_iso()
    entry = {
        "id": str(uuid4()),
        "created_at": now,
        "updated_at": now,
        "title": str(title or "").strip() or "Senza titolo",
        "content": str(content or "").strip(),
        "share_status": "private",
        "shared_at": None,
        "revoked_at": None,
        "source": PRIVATE_AREA_SOURCE,
    }
    wellness[PRIVATE_AREA_KEY].append(entry)
    return deepcopy(entry)


def _find_entry(wellness: dict[str, Any], entry_id: str) -> dict[str, Any] | None:
    for entry in _entries(wellness):
        if entry.get("id") == entry_id:
            return entry
    return None


def update_private_entry(wellness: dict[str, Any], entry_id: str, title: str, content: str) -> dict[str, Any] | None:
    entry = _find_entry(wellness, entry_id)
    if not entry or entry.get("share_status", "private") != "private":
        return None
    entry["title"] = str(title or "").strip() or "Senza titolo"
    entry["content"] = str(content or "").strip()
    entry["updated_at"] = _now_iso()
    return deepcopy(entry)


def share_private_entry(wellness: dict[str, Any], entry_id: str) -> dict[str, Any] | None:
    entry = _find_entry(wellness, entry_id)
    if not entry:
        return None
    now = _now_iso()
    entry["share_status"] = "shared"
    entry["shared_at"] = entry.get("shared_at") or now
    entry["revoked_at"] = None
    entry["updated_at"] = now
    return deepcopy(entry)


def revoke_shared_entry(wellness: dict[str, Any], entry_id: str) -> dict[str, Any] | None:
    entry = _find_entry(wellness, entry_id)
    if not entry or entry.get("share_status") != "shared":
        return None
    now = _now_iso()
    entry["share_status"] = "revoked"
    entry["revoked_at"] = now
    entry["updated_at"] = now
    return deepcopy(entry)


def delete_private_entry(wellness: dict[str, Any], entry_id: str) -> bool:
    entries = _entries(wellness)
    initial = len(entries)
    wellness[PRIVATE_AREA_KEY] = [entry for entry in entries if entry.get("id") != entry_id]
    return len(wellness[PRIVATE_AREA_KEY]) != initial
