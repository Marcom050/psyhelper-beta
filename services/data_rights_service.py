import os
from datetime import UTC, datetime
from uuid import uuid4

from database.json_storage import atomic_write_json, load_json_file

REQUESTS_PATH = os.path.expanduser("~/psyhelper_data/data_rights_requests.json")
VALID_TYPES = {"export", "delete", "retention", "processing_restriction"}
VALID_STATUS = {"requested", "processing", "completed", "rejected", "cancelled"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _load() -> list[dict]:
    if not os.path.exists(REQUESTS_PATH):
        return []
    data = load_json_file(REQUESTS_PATH)
    return data if isinstance(data, list) else []


def _save(items: list[dict]):
    os.makedirs(os.path.dirname(REQUESTS_PATH), exist_ok=True)
    atomic_write_json(REQUESTS_PATH, items)


def create_request(request_type: str, subject_username: str, tenant_id: str, requested_by: str, metadata: dict | None = None) -> dict:
    if request_type not in VALID_TYPES:
        raise ValueError("invalid request_type")
    item = {
        "request_id": str(uuid4()),
        "request_type": request_type,
        "subject_username": subject_username,
        "tenant_id": tenant_id,
        "requested_by": requested_by,
        "status": "requested",
        "created_at": _now(),
        "completed_at": None,
        "metadata": metadata or {},
    }
    items = _load()
    items.append(item)
    _save(items)
    return item


def list_requests(tenant_id: str | None = None) -> list[dict]:
    items = _load()
    if tenant_id:
        items = [i for i in items if i.get("tenant_id") == tenant_id]
    return items


def get_request(request_id: str) -> dict | None:
    for item in _load():
        if item.get("request_id") == request_id:
            return item
    return None


def update_request_status(request_id: str, status: str, metadata: dict | None = None) -> dict | None:
    if status not in VALID_STATUS:
        raise ValueError("invalid status")
    items = _load()
    out = None
    for item in items:
        if item.get("request_id") == request_id:
            item["status"] = status
            if metadata:
                item["metadata"] = {**(item.get("metadata") or {}), **metadata}
            if status in {"completed", "rejected", "cancelled"}:
                item["completed_at"] = _now()
            out = item
            break
    if out:
        _save(items)
    return out
