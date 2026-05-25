"""Service helpers for post free-consultation onboarding flow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

ONBOARDING_STEPS = ("baseline", "goals", "diary", "cbt", "next_session_note")
DEFAULT_EXPIRY_DAYS = 21


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _exp_iso(days: int = DEFAULT_EXPIRY_DAYS) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(timespec="seconds")


def ensure_post_consultation_onboarding(wellness: dict[str, Any]) -> dict[str, Any]:
    store = wellness.setdefault("post_consultation_onboardings", [])
    for item in store:
        if item.get("status") in {"active", "completed"}:
            return item
    onboarding = {
        "id": f"pco_{uuid4().hex[:12]}",
        "status": "active",
        "created_at": _now_iso(),
        "expires_at": _exp_iso(),
        "steps": {name: {"completed": False, "data": {}} for name in ONBOARDING_STEPS},
        "summary": {},
    }
    store.append(onboarding)
    return onboarding


def progress(onboarding: dict[str, Any]) -> tuple[int, int]:
    steps = onboarding.get("steps", {})
    completed = sum(1 for step in ONBOARDING_STEPS if steps.get(step, {}).get("completed"))
    return completed, len(ONBOARDING_STEPS)


def save_step(onboarding: dict[str, Any], step: str, data: dict[str, Any]) -> dict[str, Any]:
    if step not in ONBOARDING_STEPS:
        raise ValueError(f"Unsupported step: {step}")
    onboarding.setdefault("steps", {}).setdefault(step, {})
    onboarding["steps"][step]["completed"] = True
    onboarding["steps"][step]["data"] = data
    completed, total = progress(onboarding)
    onboarding["updated_at"] = _now_iso()
    onboarding["progress"] = {"completed": completed, "total": total}
    if completed == total:
        onboarding["status"] = "completed"
    return onboarding


def build_second_session_summary(onboarding: dict[str, Any]) -> dict[str, Any]:
    steps = onboarding.get("steps", {})
    summary = {
        "disclaimer": (
            "Questo riepilogo non è diagnostico: raccoglie materiali condivisi dal paziente "
            "per supportare la prossima seduta."
        ),
        "baseline": steps.get("baseline", {}).get("data", {}),
        "goals": steps.get("goals", {}).get("data", {}),
        "diary": steps.get("diary", {}).get("data", {}),
        "cbt_entry": steps.get("cbt", {}).get("data", {}),
        "next_session_note": steps.get("next_session_note", {}).get("data", {}),
        "points_to_resume": steps.get("next_session_note", {}).get("data", {}).get("points_to_resume", ""),
    }
    onboarding["summary"] = summary
    return summary
