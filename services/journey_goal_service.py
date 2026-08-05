"""Deterministic, UI-independent helpers for shared journey goals."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
import unicodedata
from typing import Any, Iterable, Mapping
from uuid import UUID, uuid4, uuid5


GOAL_NAMESPACE = UUID("bac32fd3-0180-49f7-a196-0af0a670ea3e")
EMPTY_BASELINE = "Il punto di partenza si completerà con le informazioni inserite durante il percorso."
EMPTY_PROGRESS = "I passi avanti compariranno qui man mano che verranno inserite nuove informazioni e il terapeuta aggiornerà gli obiettivi."


class JourneyGoalError(ValueError):
    pass


class JourneyGoalPermissionError(PermissionError):
    pass


def goal_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _clean_title(value: Any) -> str:
    return " ".join(str(value or "").split()).strip(" ;,.-")


def normalize_goal(goal: Mapping[str, Any]) -> dict[str, Any] | None:
    title = _clean_title(goal.get("title") or goal.get("goal") or goal.get("text"))
    if not title:
        return None
    source = str(goal.get("source") or "profile")
    created_at = str(goal.get("created_at") or datetime.now(timezone.utc).isoformat())
    stable_id = str(goal.get("id") or uuid5(GOAL_NAMESPACE, f"{source}:{goal_key(title)}"))
    try:
        UUID(stable_id)
    except (ValueError, TypeError):
        stable_id = str(uuid5(GOAL_NAMESPACE, f"legacy:{stable_id}:{goal_key(title)}"))
    status = "achieved" if goal.get("status") == "achieved" else "active"
    return {
        "id": stable_id,
        "title": title,
        "created_at": created_at,
        "created_by": str(goal.get("created_by") or ("therapist" if source == "therapist" else "patient")),
        "source": source if source in {"patient_manual", "onboarding", "profile", "therapist"} else "profile",
        "status": status,
        "achieved_at": goal.get("achieved_at") if status == "achieved" else None,
        "achieved_by": goal.get("achieved_by") if status == "achieved" else None,
        "therapist_note": _clean_title(goal.get("therapist_note"))[:300],
    }


def normalize_journey_goals(wellness: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize legacy data in place and remove obvious title duplicates."""
    unique: dict[str, dict[str, Any]] = {}
    for raw in wellness.get("journey_goals") or []:
        if not isinstance(raw, Mapping):
            continue
        goal = normalize_goal(raw)
        if goal and goal_key(goal["title"]) not in unique:
            unique[goal_key(goal["title"])] = goal
    wellness["journey_goals"] = list(unique.values())
    return wellness["journey_goals"]


def _values(container: Mapping[str, Any] | None, paths: Iterable[tuple[str, ...]]) -> list[Any]:
    found = []
    for path in paths:
        value: Any = container or {}
        for part in path:
            if not isinstance(value, Mapping):
                value = None
                break
            value = value.get(part)
        if value not in (None, "", [], {}):
            found.append(value)
    return found


def _text_items(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [item for child in value for item in _text_items(child)]
    if isinstance(value, Mapping):
        return []
    text = _clean_title(value)
    if not text:
        return []
    parts = re.split(r"(?:\r?\n|[;•])", text)
    return [_clean_title(part) for part in parts if _clean_title(part)]


GOAL_PATHS = (
    ("obiettivi",), ("goals",), ("initial_goals",), ("initial_baseline", "goals"),
    ("initial_baseline", "obiettivi"),
)
ONBOARDING_GOAL_PATHS = (
    ("goals", "goals_text"), ("goals", "short_term_priority"), ("goals", "main_goal"),
    ("goals", "track"),
    ("steps", "goals", "data", "goals_text"), ("steps", "goals", "data", "short_term_priority"),
    ("steps", "goals", "data", "main_goal"), ("steps", "goals", "data", "track"),
)
ONBOARDING_COMMITMENT_PATHS = (
    ("goals", "personal_commitment"),
    ("steps", "goals", "data", "personal_commitment"),
)


def _onboarding_commitment_keys(wellness: Mapping[str, Any] | None) -> set[str]:
    """Return patient commitments that must remain separate from therapy goals."""
    keys: set[str] = set()
    for onboarding in (wellness or {}).get("post_consultation_onboardings") or []:
        for value in _values(onboarding, ONBOARDING_COMMITMENT_PATHS):
            keys.update(goal_key(title) for title in _text_items(value))
    return keys


def extract_initial_goals(profile: Mapping[str, Any] | None, wellness: Mapping[str, Any] | None) -> list[str]:
    candidates = _values(profile, GOAL_PATHS)
    for onboarding in (wellness or {}).get("post_consultation_onboardings") or []:
        candidates.extend(_values(onboarding, ONBOARDING_GOAL_PATHS))
    candidates.extend(_values(wellness, (("onboarding", "goals"), ("onboarding", "obiettivi"))))
    for event in (wellness or {}).get("timeline_events") or []:
        event_type = goal_key(event.get("type") or event.get("tipo"))
        if event_type in {"goal", "obiettivo", "journey goal"}:
            candidates.append(event.get("title") or event.get("titolo"))
    unique: dict[str, str] = {}
    for candidate in candidates:
        for title in _text_items(candidate):
            unique.setdefault(goal_key(title), title)
    return list(unique.values())


def materialize_initial_goals(wellness: dict[str, Any], profile: Mapping[str, Any] | None) -> bool:
    goals = normalize_journey_goals(wellness)
    changed = False

    commitment_keys = _onboarding_commitment_keys(wellness)
    if commitment_keys:
        filtered_goals = [
            goal for goal in goals
            if not (
                goal.get("source") == "onboarding"
                and goal_key(goal.get("title")) in commitment_keys
            )
        ]
        if len(filtered_goals) != len(goals):
            wellness["journey_goals"] = filtered_goals
            goals = filtered_goals
            changed = True

    existing = {goal_key(goal["title"]) for goal in goals}
    for title in extract_initial_goals(profile, wellness):
        key = goal_key(title)
        if key in existing:
            continue
        goals.append(normalize_goal({
            "id": str(uuid5(GOAL_NAMESPACE, f"initial:{key}")), "title": title,
            "created_at": "1970-01-01T00:00:00+00:00", "created_by": "patient", "source": "onboarding",
        }))
        existing.add(key)
        changed = True
    return changed


def create_patient_goal(wellness: dict[str, Any], title: str) -> dict[str, Any]:
    title = _clean_title(title)
    if not title:
        raise JourneyGoalError("Inserisci il testo dell’obiettivo.")
    if len(title) > 240:
        raise JourneyGoalError("L’obiettivo deve contenere al massimo 240 caratteri.")
    goals = normalize_journey_goals(wellness)
    if goal_key(title) in {goal_key(goal["title"]) for goal in goals}:
        raise JourneyGoalError("Questo obiettivo è già presente nel percorso.")
    goal = normalize_goal({"id": str(uuid4()), "title": title, "created_at": datetime.now(timezone.utc).isoformat(), "created_by": "patient", "source": "patient_manual"})
    goals.append(goal)
    return deepcopy(goal)


def update_goal_by_therapist(wellness: dict[str, Any], goal_id: str, *, achieved: bool, note: str,
                             actor_username: str, patient_owner: str, actor_role: str = "therapist") -> dict[str, Any]:
    if actor_role != "therapist" or actor_username != patient_owner:
        raise JourneyGoalPermissionError("Solo il terapeuta proprietario può aggiornare l’obiettivo.")
    if len(str(note or "").strip()) > 300:
        raise JourneyGoalError("La nota deve contenere al massimo 300 caratteri.")
    for goal in normalize_journey_goals(wellness):
        if goal["id"] == goal_id:
            goal["status"] = "achieved" if achieved else "active"
            goal["achieved_at"] = datetime.now(timezone.utc).isoformat() if achieved else None
            goal["achieved_by"] = actor_username if achieved else None
            goal["therapist_note"] = str(note or "").strip()
            return deepcopy(goal)
    raise JourneyGoalError("Obiettivo non trovato.")


def active_goals(wellness: dict[str, Any]) -> list[dict[str, Any]]:
    return [deepcopy(goal) for goal in normalize_journey_goals(wellness) if goal["status"] == "active"]


def achieved_goals(wellness: dict[str, Any]) -> list[dict[str, Any]]:
    return [deepcopy(goal) for goal in normalize_journey_goals(wellness) if goal["status"] == "achieved"]


def build_starting_point(profile: Mapping[str, Any] | None, wellness: Mapping[str, Any] | None) -> dict[str, Any]:
    onboarding = ((wellness or {}).get("post_consultation_onboardings") or [{}])[-1]
    baseline_paths = (
        ("initial_baseline",),
        ("initial_baseline", "perceived_difficulty"), ("initial_baseline", "mood"),
        ("initial_baseline", "anxiety"), ("initial_baseline", "stress"),
    )
    detail_paths = (
        ("steps", "baseline", "data", "perceived_difficulty"), ("steps", "baseline", "data", "mood"),
        ("steps", "baseline", "data", "anxiety"), ("steps", "baseline", "data", "stress"),
        ("steps", "diary", "data", "habits_to_change"), ("steps", "cbt_entry", "data", "automatic_thought"),
        ("steps", "goals", "data", "first_change"),
    )
    details = []
    for value in _values(profile, baseline_paths) + _values(onboarding, detail_paths):
        details.extend(_text_items(value))
    # Historic top-level aliases.
    details.extend(item for value in _values(wellness, (("baseline", "perceived_difficulty"), ("baseline", "mood"), ("baseline", "anxiety"), ("baseline", "stress"), ("diary", "habits_to_change"), ("cbt_entry", "automatic_thought"))) for item in _text_items(value))
    details = list(dict.fromkeys(details))[:5]
    goals = extract_initial_goals(profile, wellness)[:5]
    return {"details": details, "goals": goals, "empty": not details and not goals, "empty_message": EMPTY_BASELINE}


def build_patient_progress_recap(wellness: dict[str, Any], journey: Mapping[str, Any]) -> dict[str, Any]:
    reached = achieved_goals(wellness)
    automatic = list(journey.get("progress_markers") or [])
    completed = int((journey.get("current_snapshot") or {}).get("homework_completed") or 0)
    if completed:
        automatic.append(f"Hai completato {completed} homework.")
    for event in journey.get("timeline_events") or []:
        if event.get("type") in {"step_forward", "improvement", "maintained_progress"}:
            text = _clean_title(event.get("description") or event.get("title"))
            if text:
                automatic.append(f"Cambiamento emerso dalle compilazioni: {text}")
    automatic = list(dict.fromkeys(automatic))[:6]
    return {"achieved_goals": reached, "automatic_signals": automatic, "empty": not reached and not automatic, "empty_message": EMPTY_PROGRESS}


def source_label(source: str) -> str:
    return {"patient_manual": "Aggiunto da te", "therapist": "Concordato con il terapeuta", "onboarding": "Indicato all’inizio del percorso", "profile": "Indicato all’inizio del percorso"}.get(source, "Indicato all’inizio del percorso")
