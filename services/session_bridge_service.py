"""Pure domain helpers for the patient Session Bridge.

The bridge stores only references to existing wellness items.  Display data is
resolved on demand, so source text is neither duplicated nor made stale.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import quote

from services.homework_service import homework_readable_summary


REFERENCE_PREFIX = "session_bridge"
ALLOWED_SOURCE_TYPES = frozenset({
    "next_session", "shared_private_area", "homework_submission",
    "diary_entry", "journey_goal", "timeline_summary",
})
DEFAULT_MAX_ITEMS = 5
DEFAULT_TEXT_MAX_LENGTH = 500


class SessionBridgeValidationError(ValueError):
    """Raised when a Session Bridge payload violates its domain rules."""


class SessionBridgeReferenceError(SessionBridgeValidationError):
    """Raised when a source reference cannot be resolved safely."""


@dataclass(frozen=True)
class RecencyPolicy:
    """Temporary explicit policy until reliable session entities exist."""

    homework_days: int = 30
    diary_days: int = 30
    timeline_days: int = 60

    def __post_init__(self) -> None:
        if min(self.homework_days, self.diary_days, self.timeline_days) < 0:
            raise ValueError("Recency windows cannot be negative")


@dataclass(frozen=True)
class SessionBridgePayload:
    """Minimal persistable bridge payload; it deliberately contains no copy."""

    selected_refs: tuple[str, ...]
    priority_ref: str
    optional_text: str = ""
    week_rating: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_refs": list(self.selected_refs),
            "priority_ref": self.priority_ref,
            "optional_text": self.optional_text,
            "week_rating": self.week_rating,
        }


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _legacy_identity(source_type: str, item: Mapping[str, Any]) -> str:
    """Build the strongest source-specific identity available without writing an ID.

    Stable source fields are preferred so later content/status edits do not
    invalidate a saved reference. If none exist, the canonical record digest is
    the minimum unavoidable fallback. Exact duplicate legacy records are
    intentionally indistinguishable and are collapsed by the candidate builder:
    without changing the source there is no honest, order-independent way to
    tell those records apart.
    """
    identity_fields = {
        "next_session": ("created_at", "updated_at", "type"),
        "shared_private_area": ("created_at", "shared_at", "updated_at"),
        "homework_submission": ("assignment_id", "submitted_at", "created_at"),
        "diary_entry": ("data", "date", "created_at", "creata_il"),
        "journey_goal": ("created_at", "source"),
        "timeline_summary": ("date", "data", "created_at", "type", "tipo"),
    }[source_type]
    stable = {field: item[field] for field in identity_fields if item.get(field) not in (None, "")}
    seed = _canonical(stable) if stable else _canonical(item)
    digest = hashlib.sha256(seed.encode()).hexdigest()[:24]
    return f"{quote(seed, safe='')}:{digest}"


def source_reference(source_type: str, item: Mapping[str, Any], *, legacy_index: int = 0) -> str:
    """Return a namespaced reference, including a stable legacy fallback."""
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise SessionBridgeValidationError(f"Unsupported source type: {source_type}")
    raw_id = item.get("id")
    if raw_id not in (None, ""):
        identifier = f"id:{quote(str(raw_id), safe='')}"
    else:
        # ``legacy_index`` is retained in the public signature for backwards
        # compatibility, but no longer influences newly generated references.
        identifier = f"legacy:{_legacy_identity(source_type, item)}"
    return f"{REFERENCE_PREFIX}:{source_type}:{identifier}"


def _candidate(source_type: str, item: Mapping[str, Any], index: int, *, title: Any,
               content: Any, occurred_at: Any, rank: int) -> dict[str, Any] | None:
    title, content = str(title or "").strip(), str(content or "").strip()
    if not title and not content:
        return None
    return {
        "ref": source_reference(source_type, item, legacy_index=index),
        "source_type": source_type,
        "title": title or "Elemento del percorso",
        "content": content,
        "occurred_at": str(occurred_at or ""),
        "rank": rank,
        "selected": False,
    }


def _recent(item: Mapping[str, Any], fields: Sequence[str], days: int, now: datetime) -> bool:
    value = next((item.get(field) for field in fields if item.get(field)), None)
    parsed = _timestamp(value)
    return parsed is not None and parsed >= now - timedelta(days=days) and parsed <= now


def _mapping_items(value: Any) -> Iterable[tuple[int, Mapping[str, Any]]]:
    if not isinstance(value, list):
        return ()
    return ((index, item) for index, item in enumerate(value) if isinstance(item, Mapping))


def _build_candidates(wellness: Mapping[str, Any] | None, *, policy: RecencyPolicy,
                      now: datetime, apply_recency: bool) -> list[dict[str, Any]]:
    """Build display candidates without mutating or persisting the wellness input."""
    wellness = wellness or {}
    candidates: list[dict[str, Any]] = []

    # Explicit patient notes for the next session, currently produced by onboarding.
    for oi, onboarding in _mapping_items(wellness.get("post_consultation_onboardings")):
        data = (((onboarding.get("steps") or {}).get("next_session_note") or {}).get("data") or {})
        if isinstance(data, Mapping):
            for fi, field in enumerate(("points_to_resume", "additional_info")):
                text = data.get(field)
                if text:
                    synthetic = {"id": f"{onboarding.get('id')}:{field}"} if onboarding.get("id") else {field: text, "onboarding_index": oi}
                    candidate = _candidate("next_session", synthetic, oi * 2 + fi, title="Per la prossima seduta",
                                           content=text, occurred_at=onboarding.get("updated_at") or onboarding.get("created_at"), rank=0)
                    if candidate:
                        candidates.append(candidate)

    for index, item in _mapping_items(wellness.get("private_area_entries")):
        if item.get("share_status") != "shared" or item.get("revoked_at"):
            continue
        # Defensive boundary: therapist-authored/private therapist notes never enter the bridge.
        if str(item.get("created_by") or item.get("author_role") or "patient").lower() == "therapist":
            continue
        candidate = _candidate("shared_private_area", item, index, title=item.get("title"), content=item.get("content"),
                               occurred_at=item.get("shared_at") or item.get("updated_at"), rank=10)
        if candidate:
            candidates.append(candidate)

    for index, item in _mapping_items(wellness.get("homework_submissions")):
        if not apply_recency or _recent(item, ("submitted_at", "created_at", "date"), policy.homework_days, now):
            free_note = item.get("free_note") or item.get("notes") or item.get("note")
            content = free_note or homework_readable_summary(item, max_chars=10_000)
            candidate = _candidate("homework_submission", item, index, title=item.get("template") or "Homework completato",
                                   content=content, occurred_at=item.get("submitted_at") or item.get("created_at"), rank=20)
            if candidate:
                candidates.append(candidate)

    for index, item in _mapping_items(wellness.get("mood_entries")):
        if not apply_recency or _recent(item, ("data", "date", "created_at", "creata_il"), policy.diary_days, now):
            content = item.get("note") or item.get("notes") or item.get("pensiero_automatico") or item.get("trigger") or item.get("comportamento")
            candidate = _candidate("diary_entry", item, index, title=item.get("title") or item.get("umore") or "Diario CBT",
                                   content=content, occurred_at=item.get("data") or item.get("date") or item.get("created_at"), rank=30)
            if candidate:
                candidates.append(candidate)

    for index, item in _mapping_items(wellness.get("journey_goals")):
        # Therapist notes are intentionally not exposed; only goal/progress fields are used.
        content = item.get("progress") or item.get("progress_text") or item.get("title") or item.get("goal") or item.get("text")
        candidate = _candidate("journey_goal", item, index, title=item.get("title") or item.get("goal") or "Obiettivo",
                               content=content, occurred_at=item.get("updated_at") or item.get("achieved_at") or item.get("created_at"), rank=40)
        if candidate:
            candidates.append(candidate)

    for index, item in _mapping_items(wellness.get("timeline_events")):
        if not apply_recency or _recent(item, ("date", "data", "created_at"), policy.timeline_days, now):
            candidate = _candidate("timeline_summary", item, index, title=item.get("title") or item.get("titolo") or "Sintesi del percorso",
                                   content=item.get("description") or item.get("dettaglio"), occurred_at=item.get("date") or item.get("data"), rank=50)
            if candidate:
                candidates.append(candidate)

    # Stable priority order, with recent items first inside the same source band.
    candidates.sort(key=lambda c: (c["rank"], -(_timestamp(c["occurred_at"]) or datetime.min.replace(tzinfo=timezone.utc)).timestamp(), c["ref"]))
    # Exact legacy duplicates have the same source identity and cannot be
    # distinguished without an unstable positional index or a persisted ID.
    return list({candidate["ref"]: candidate for candidate in candidates}.values())


def build_bridge_candidates(wellness: Mapping[str, Any] | None, *, policy: RecencyPolicy | None = None,
                            now: datetime | None = None) -> list[dict[str, Any]]:
    """Build new-selection candidates; recency is applied only at this stage."""
    policy = policy or RecencyPolicy()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return _build_candidates(wellness, policy=policy, now=current, apply_recency=True)


def validate_bridge_payload(payload: Mapping[str, Any] | SessionBridgePayload, *, max_items: int = DEFAULT_MAX_ITEMS,
                            text_max_length: int = DEFAULT_TEXT_MAX_LENGTH) -> SessionBridgePayload:
    data = payload.to_dict() if isinstance(payload, SessionBridgePayload) else payload
    refs = data.get("selected_refs", [])
    if not isinstance(refs, (list, tuple)) or not all(isinstance(ref, str) and ref for ref in refs):
        raise SessionBridgeValidationError("selected_refs must be a list of references")
    if len(refs) != len(set(refs)):
        raise SessionBridgeValidationError("Duplicate selections are not allowed")
    if len(refs) > max_items:
        raise SessionBridgeValidationError(f"At most {max_items} items may be selected")
    priority = data.get("priority_ref")
    if not isinstance(priority, str) or not priority:
        raise SessionBridgeValidationError("Exactly one priority is required")
    if priority not in refs:
        raise SessionBridgeValidationError("The priority must be one of the selected items")
    for ref in refs:
        parts = ref.split(":", 3)
        if len(parts) != 4 or parts[0] != REFERENCE_PREFIX or parts[1] not in ALLOWED_SOURCE_TYPES:
            raise SessionBridgeValidationError(f"Unsupported source reference: {ref}")
    optional_text = data.get("optional_text", "")
    if optional_text is None:
        optional_text = ""
    if not isinstance(optional_text, str) or len(optional_text) > text_max_length:
        raise SessionBridgeValidationError(f"optional_text must contain at most {text_max_length} characters")
    week_rating = data.get("week_rating")
    if week_rating is not None and (type(week_rating) is not int or not 1 <= week_rating <= 5):
        raise SessionBridgeValidationError("week_rating must be null or an integer from 1 to 5")
    return SessionBridgePayload(tuple(refs), priority, optional_text, week_rating)


def empty_session_bridge() -> dict[str, Any]:
    """Return the canonical state used when a legacy document has no bridge."""
    return {"selected_refs": [], "priority_ref": None, "optional_text": "", "week_rating": None}


def validate_session_bridge_state(payload: Mapping[str, Any] | SessionBridgePayload) -> dict[str, Any]:
    """Validate the persistable state, including its canonical empty form."""
    data = payload.to_dict() if isinstance(payload, SessionBridgePayload) else payload
    if data.get("selected_refs") == [] and data.get("priority_ref") is None:
        optional_text = data.get("optional_text", "")
        if not isinstance(optional_text, str) or len(optional_text) > DEFAULT_TEXT_MAX_LENGTH:
            raise SessionBridgeValidationError(
                f"optional_text must contain at most {DEFAULT_TEXT_MAX_LENGTH} characters"
            )
        week_rating = data.get("week_rating")
        if week_rating is not None and (type(week_rating) is not int or not 1 <= week_rating <= 5):
            raise SessionBridgeValidationError("week_rating must be null or an integer from 1 to 5")
        return {**empty_session_bridge(), "optional_text": optional_text, "week_rating": week_rating}
    return validate_bridge_payload(payload).to_dict()


def get_session_bridge(wellness: Mapping[str, Any] | None) -> dict[str, Any]:
    """Read and validate the persisted state without mutating the document."""
    if not isinstance(wellness, Mapping) or "session_bridge" not in wellness:
        return empty_session_bridge()
    stored = wellness["session_bridge"]
    if not isinstance(stored, Mapping):
        raise SessionBridgeValidationError("session_bridge must be an object")
    return validate_session_bridge_state(stored)


def save_session_bridge(wellness: dict[str, Any], payload: Mapping[str, Any] | SessionBridgePayload) -> dict[str, Any]:
    """Validate and replace only the current Session Bridge state."""
    valid = validate_session_bridge_state(payload)
    wellness["session_bridge"] = valid
    return valid


def resolve_bridge_references(wellness: Mapping[str, Any] | None, refs: Sequence[str], *,
                              policy: RecencyPolicy | None = None, now: datetime | None = None) -> list[dict[str, Any]]:
    policy = policy or RecencyPolicy()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    candidates = {candidate["ref"]: candidate for candidate in _build_candidates(
        wellness, policy=policy, now=current, apply_recency=False
    )}
    missing = [ref for ref in refs if ref not in candidates]
    if missing:
        raise SessionBridgeReferenceError(f"Unresolvable Session Bridge reference(s): {', '.join(missing)}")
    return [candidates[ref].copy() for ref in refs]


def _unavailable_reason(wellness: Mapping[str, Any] | None, ref: str) -> str:
    """Classify privacy removals without ever returning their source content."""
    if ref.startswith(f"{REFERENCE_PREFIX}:shared_private_area:"):
        for index, item in _mapping_items((wellness or {}).get("private_area_entries")):
            if source_reference("shared_private_area", item, legacy_index=index) != ref:
                continue
            if item.get("share_status") == "revoked" or item.get("revoked_at"):
                return "revoked"
            if item.get("share_status") != "shared":
                return "not_shared"
            if str(item.get("created_by") or item.get("author_role") or "patient").lower() == "therapist":
                return "privacy_restricted"
    return "source_unavailable"


def build_bridge_preview(wellness: Mapping[str, Any] | None, payload: Mapping[str, Any] | SessionBridgePayload, *,
                         policy: RecencyPolicy | None = None, now: datetime | None = None,
                         max_items: int = DEFAULT_MAX_ITEMS, text_max_length: int = DEFAULT_TEXT_MAX_LENGTH) -> dict[str, Any]:
    """Calculate an ephemeral preview by resolving source data at read time."""
    valid = validate_bridge_payload(payload, max_items=max_items, text_max_length=text_max_length)
    policy = policy or RecencyPolicy()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    available = {candidate["ref"]: candidate for candidate in _build_candidates(
        wellness, policy=policy, now=current, apply_recency=False
    )}
    items = [available[ref].copy() for ref in valid.selected_refs if ref in available]
    unavailable_refs = [
        {"ref": ref, "reason": _unavailable_reason(wellness, ref)}
        for ref in valid.selected_refs if ref not in available
    ]
    for item in items:
        item.pop("selected", None)
        item["is_priority"] = item["ref"] == valid.priority_ref
    resolved_priority = valid.priority_ref if valid.priority_ref in available else None
    return {
        "items": items,
        "priority_ref": resolved_priority,
        "optional_text": valid.optional_text,
        "unavailable_refs": unavailable_refs,
    }


# Concise aliases for callers that use the domain name rather than the UI name.
build_session_bridge_candidates = build_bridge_candidates
build_session_bridge_preview = build_bridge_preview
validate_session_bridge_payload = validate_bridge_payload
resolve_session_bridge_references = resolve_bridge_references
