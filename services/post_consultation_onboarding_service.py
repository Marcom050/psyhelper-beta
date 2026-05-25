from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any
import uuid

from api.exceptions import AuthenticationError, NotFoundError
from services import auth_service

DISCLAIMER = "Questo riepilogo non è una diagnosi e non sostituisce la valutazione clinica del professionista. Riordina solo le informazioni inserite dal paziente per facilitare la preparazione della seduta."


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(UTC)


def _bundle(username: str) -> dict[str, Any]:
    if not auth_service.user_exists(username):
        raise NotFoundError("User not found")
    return auth_service.load_account_bundle(username)


def _save(username: str, bundle: dict[str, Any]) -> None:
    auth_service.save_account_bundle(username, bundle["profile"], bundle["messages"], bundle["wellness"])


def _get_onboarding(wellness: dict[str, Any], onboarding_id: str) -> dict[str, Any]:
    for item in wellness.get("post_consultation_onboardings", []):
        if item.get("id") == onboarding_id:
            return item
    raise NotFoundError("Onboarding not found")


def _progress(onboarding: dict[str, Any]) -> dict[str, Any]:
    steps = {
        "baseline": bool(onboarding.get("baseline")),
        "goals": len(onboarding.get("goals", [])) > 0,
        "diary": len(onboarding.get("diary_entries", [])) >= 3,
        "cbt_entry": bool(onboarding.get("cbt_entry")),
        "next_session_note": bool(onboarding.get("next_session_note", {}).get("must_discuss")),
    }
    completed = sum(1 for v in steps.values() if v)
    onboarding["steps_status"] = steps
    onboarding["completed_steps"] = completed
    onboarding["total_steps"] = 5
    onboarding["completion_percent"] = int(completed / 5 * 100)
    return onboarding


def _refresh_status(onboarding: dict[str, Any], now: datetime | None = None) -> None:
    ts = _now(now)
    if onboarding.get("status") != "completed" and onboarding.get("expires_at") and datetime.fromisoformat(onboarding["expires_at"]) < ts:
        onboarding["status"] = "expired"
    _progress(onboarding)
    if onboarding["completed_steps"] == 5 and onboarding.get("status") != "expired":
        onboarding["status"] = "completed"
        onboarding["completed_at"] = ts.isoformat()
    elif onboarding.get("status") == "not_started":
        onboarding["status"] = "active"
    onboarding["updated_at"] = ts.isoformat()


def activate_onboarding(*, therapist_id: str, patient_id: str, tenant_id: str, now: datetime | None = None) -> dict[str, Any]:
    ts = _now(now)
    bundle = _bundle(patient_id)
    wellness = bundle["wellness"]
    wellness.setdefault("post_consultation_onboardings", [])
    onboarding = {
        "id": f"pco_{uuid.uuid4().hex[:12]}", "tenant_id": tenant_id, "therapist_id": therapist_id, "patient_id": patient_id,
        "status": "active", "activated_at": ts.isoformat(), "expires_at": (ts + timedelta(days=3)).isoformat(),
        "completed_at": None, "created_at": ts.isoformat(), "updated_at": ts.isoformat(),
        "baseline": {}, "goals": [], "diary_entries": [], "cbt_entry": {}, "next_session_note": {},
    }
    _progress(onboarding)
    wellness["post_consultation_onboardings"].append(onboarding)
    _save(patient_id, bundle)
    return onboarding


def get_onboarding(patient_id: str, onboarding_id: str) -> dict[str, Any]:
    bundle = _bundle(patient_id)
    onboarding = _get_onboarding(bundle["wellness"], onboarding_id)
    _refresh_status(onboarding)
    _save(patient_id, bundle)
    return onboarding


def update_step(patient_id: str, onboarding_id: str, step: str, payload: Any) -> dict[str, Any]:
    bundle = _bundle(patient_id)
    onboarding = _get_onboarding(bundle["wellness"], onboarding_id)
    if step == "baseline": onboarding["baseline"] = payload
    elif step == "goals": onboarding["goals"] = payload[:3]
    elif step == "diary_entries": onboarding["diary_entries"] = payload
    elif step == "cbt_entry": onboarding["cbt_entry"] = payload
    elif step == "next_session_note": onboarding["next_session_note"] = payload
    _refresh_status(onboarding)
    _save(patient_id, bundle)
    return onboarding


def assert_therapist_access(onboarding: dict[str, Any], actor_username: str, actor_tenant_id: str) -> None:
    if onboarding.get("therapist_id") != actor_username or onboarding.get("tenant_id") != actor_tenant_id:
        raise AuthenticationError("Not authorized for requested onboarding")


def assert_patient_access(onboarding: dict[str, Any], actor_username: str, actor_tenant_id: str) -> None:
    if onboarding.get("patient_id") != actor_username or onboarding.get("tenant_id") != actor_tenant_id:
        raise AuthenticationError("Not authorized for requested onboarding")


def build_post_consultation_summary(patient_id: str, therapist_id: str, onboarding_id: str) -> dict[str, Any]:
    onboarding = get_onboarding(patient_id, onboarding_id)
    if onboarding.get("therapist_id") != therapist_id:
        raise AuthenticationError("Not authorized for requested onboarding")
    diary = onboarding.get("diary_entries", [])
    emotions = [d.get("emotion", "").strip() for d in diary if d.get("emotion")]
    thought = [d.get("automatic_thought", "").strip() for d in diary if d.get("automatic_thought")]
    behaviors = [d.get("behavior", "").strip() for d in diary if d.get("behavior")]
    events = [d.get("event", "").strip() for d in diary if d.get("event")]
    intensities = [int(d.get("intensity")) for d in diary if str(d.get("intensity", "")).isdigit()]
    return {
        "disclaimer": DISCLAIMER,
        "completion": {"status": onboarding.get("status"), "completed_steps": onboarding.get("completed_steps"), "total_steps": 5},
        "baseline": onboarding.get("baseline", {}),
        "goals": onboarding.get("goals", []),
        "frequent_emotions": Counter(emotions).most_common(3),
        "average_intensity": round(sum(intensities) / len(intensities), 2) if intensities else None,
        "recurring_triggers": Counter(events).most_common(3),
        "recurring_automatic_thoughts": Counter(thought).most_common(3),
        "emerging_behaviors": Counter(behaviors).most_common(3),
        "cbt_entry": onboarding.get("cbt_entry", {}),
        "must_discuss": onboarding.get("next_session_note", {}).get("must_discuss", ""),
        "hard_to_say": onboarding.get("next_session_note", {}).get("hard_to_say", ""),
        "suggested_session_points": [
            "Rivedere insieme i principali trigger riportati.",
            "Approfondire i pensieri automatici più ricorrenti.",
            "Partire dal punto che il paziente considera prioritario.",
        ],
    }
