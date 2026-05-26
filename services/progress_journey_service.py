from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Optional

import pandas as pd

from services.report_service import mood_entries_dataframe
from services.post_consultation_onboarding_service import progress as onboarding_progress

NON_DIAGNOSTIC_DISCLAIMER = (
    "Questa panoramica organizza informazioni inserite dal paziente e dati già presenti nel sistema. "
    "Non fornisce diagnosi o valutazioni cliniche automatiche."
)

PATIENT_RETENTION_NUDGE = "Anche un aggiornamento breve può aiutare il terapeuta a capire meglio come sta andando il percorso."
THERAPIST_RETENTION_NUDGE = (
    "Possibile perdita di continuità: il paziente non ha aggiornato il diario o completato homework recenti. "
    "Potrebbe essere utile riprendere motivazione e obiettivi in seduta."
)


def _to_date_label(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    return ts.strftime("%d/%m/%Y") if pd.notna(ts) else "Data non disponibile"


def normalize_progress_timeline_event(event: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    event = event or {}
    date_value = event.get("date") or event.get("data")
    raw_type = str(event.get("type") or event.get("tipo") or "note").strip().lower()
    type_aliases = {
        "homework_completed": "homework",
        "homework assegnato": "homework",
        "homework completato": "homework",
        "start": "onboarding",
        "evento clinico": "note",
    }
    normalized_type = type_aliases.get(raw_type, raw_type)
    allowed_types = {"baseline", "progress", "setback", "homework", "onboarding", "note", "session", "trigger"}
    if normalized_type not in allowed_types:
        normalized_type = "note"
    title = event.get("title") or event.get("titolo") or "Evento del percorso"
    description = event.get("description") or event.get("dettaglio") or ""
    source = event.get("source") or "progress_journey"
    non_diagnostic = bool(event.get("non_diagnostic", True))
    return {
        "date": date_value,
        "date_label": event.get("date_label") or _to_date_label(date_value),
        "type": normalized_type,
        "title": str(title),
        "description": str(description),
        "source": str(source),
        "non_diagnostic": non_diagnostic,
    }


def build_progress_journey_summary(
    wellness: Optional[Mapping[str, Any]],
    homework_data: Optional[Mapping[str, Any]] = None,
    reports_data: Optional[Mapping[str, Any]] = None,
    notes_data: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    wellness = wellness or {}
    df = mood_entries_dataframe(wellness)
    assignments = list((homework_data or {}).get("assignments", wellness.get("homework_assignments", [])))
    submissions = list((homework_data or {}).get("submissions", wellness.get("homework_submissions", [])))
    onboarding = (wellness.get("post_consultation_onboardings") or [{}])[-1] if wellness.get("post_consultation_onboardings") else {}
    baseline_step = ((onboarding.get("steps") or {}).get("baseline") or {}).get("data", {})
    goals_step = ((onboarding.get("steps") or {}).get("goals") or {}).get("data", {})

    completed_ids = {s.get("assignment_id") for s in submissions if s.get("assignment_id")}
    timeline_events: list[dict[str, Any]] = []
    progress_markers: list[str] = []
    setback_markers: list[str] = []

    baseline = {
        "mood": baseline_step.get("mood"),
        "stress": baseline_step.get("stress"),
        "anxiety": baseline_step.get("anxiety", baseline_step.get("stress")),
        "sleep": baseline_step.get("sleep"),
        "energy": baseline_step.get("energy"),
        "avoidance": baseline_step.get("avoidance"),
        "goals": [v for v in [goals_step.get("main_goal"), goals_step.get("track")] if v],
        "source": "post_consultation_onboarding" if baseline_step else "mood_entries",
    }

    if not baseline_step and not df.empty:
        first = df.iloc[0]
        baseline.update({
            "mood": first.get("umore_intensita"),
            "stress": first.get("stress"),
            "anxiety": first.get("ansia"),
            "source": "mood_entries",
        })

    now = pd.Timestamp.now().tz_localize(None).normalize()
    recent_14 = df[df["data"] >= now - pd.Timedelta(days=14)] if not df.empty else pd.DataFrame()
    recent_7 = df[df["data"] >= now - pd.Timedelta(days=7)] if not df.empty else pd.DataFrame()
    prev_7 = df[(df["data"] < now - pd.Timedelta(days=7)) & (df["data"] >= now - pd.Timedelta(days=14))] if not df.empty else pd.DataFrame()

    current_snapshot = {
        "window_days": 14,
        "recent_mood_avg": float(recent_14["umore_intensita"].mean()) if not recent_14.empty else None,
        "recent_anxiety_avg": float(recent_14["ansia"].mean()) if not recent_14.empty else None,
        "recent_stress_avg": float(recent_14["stress"].mean()) if not recent_14.empty else None,
        "homework_completed": len(completed_ids),
        "homework_assigned": len(assignments),
    }

    if baseline.get("anxiety") is not None and current_snapshot["recent_anxiety_avg"] is not None:
        delta = current_snapshot["recent_anxiety_avg"] - float(baseline["anxiety"])
        current_snapshot["anxiety_vs_baseline"] = round(delta, 2)

    if not recent_7.empty and not prev_7.empty:
        delta_anx = float(recent_7["ansia"].mean() - prev_7["ansia"].mean())
        delta_stress = float(recent_7["stress"].mean() - prev_7["stress"].mean())
        if delta_anx <= -0.7 or delta_stress <= -0.7:
            progress_markers.append("Potrebbe essere un segnale di miglioramento: nei dati recenti ansia/stress risultano in riduzione rispetto alla settimana precedente.")
            timeline_events.append({"date": now.isoformat(), "date_label": _to_date_label(now), "type": "progress", "title": "Progressi", "description": "Riduzione recente di ansia/stress da riprendere con il terapeuta.", "source": "mood_entries", "evidence_level": "medium", "non_diagnostic": True})
        if delta_anx >= 0.7 or delta_stress >= 0.7:
            setback_markers.append("Momento di difficoltà da esplorare: possibile aumento recente di ansia/stress rispetto alla settimana precedente.")
            timeline_events.append({"date": now.isoformat(), "date_label": _to_date_label(now), "type": "setback", "title": "Ricaduta", "description": "Possibile ricaduta o fase di maggiore fatica nei dati recenti.", "source": "mood_entries", "evidence_level": "medium", "non_diagnostic": True})

    trigger_counter = Counter()
    for row in (wellness.get("mood_entries") or []):
        trigger = row.get("trigger")
        if trigger:
            for part in [p.strip().lower() for p in str(trigger).split(",") if p.strip()]:
                trigger_counter[part] += 1
    recurring_triggers = [{"trigger": k, "count": v} for k, v in trigger_counter.most_common(5)]

    helpful_strategies = []
    homework_impact = []
    for assignment in assignments:
        title = assignment.get("template", "Esercizio")
        aid = assignment.get("id")
        if aid in completed_ids:
            helpful_strategies.append(f"Dopo l'esercizio '{title}', nei dati successivi compaiono informazioni utili da discutere in seduta.")
            homework_impact.append({"homework": title, "status": "completed", "note": "Potrebbe essere utile discuterne in seduta."})
            timeline_events.append({"date": assignment.get("assigned_at") or assignment.get("due_date"), "date_label": _to_date_label(assignment.get("assigned_at") or assignment.get("due_date")), "type": "homework", "title": "Homework completato", "description": title, "source": "homework_submissions", "evidence_level": "high", "non_diagnostic": True})
        else:
            homework_impact.append({"homework": title, "status": "pending", "note": "Tema da portare in seduta per capire ostacoli e supporti utili."})

    if not timeline_events:
        timeline_events.append({"date": None, "date_label": "Data non disponibile", "type": "onboarding", "title": "Inizio percorso", "description": "Avvia raccolta dati per rendere visibile l'andamento.", "source": "system", "evidence_level": "low", "non_diagnostic": True})

    # onboarding events
    if onboarding:
        timeline_events.append({"date": onboarding.get("started_at"), "date_label": _to_date_label(onboarding.get("started_at")), "type": "baseline", "title": "Baseline compilata", "description": "Informazioni iniziali inserite dal paziente.", "source": "post_consultation_onboarding", "evidence_level": "high", "non_diagnostic": True})

    timeline_events = [normalize_progress_timeline_event(event) for event in timeline_events]
    timeline_events = sorted(timeline_events, key=lambda item: str(item.get("date") or ""))

    next_session_points = []
    if progress_markers:
        next_session_points.append("Rinforzare i segnali di miglioramento osservati nelle ultime compilazioni.")
    if setback_markers:
        next_session_points.append("Esplorare i momenti di difficoltà e i possibili fattori che hanno inciso.")
    if recurring_triggers:
        next_session_points.append(f"Approfondire trigger ricorrenti: {', '.join(item['trigger'] for item in recurring_triggers[:3])}.")
    if any(item["status"] == "pending" for item in homework_impact):
        next_session_points.append("Rivedere homework non completati e definire un passo sostenibile.")
    if not next_session_points:
        next_session_points.append("Raccogliere nuovi check-in per avere una visione più concreta dell'andamento.")

    retention_alerts = []
    if recent_7.empty:
        retention_alerts.append({"type": "no_recent_entries", "severity": "medium", "therapist_copy": THERAPIST_RETENTION_NUDGE, "patient_copy": PATIENT_RETENTION_NUDGE})
    if assignments and not completed_ids:
        retention_alerts.append({"type": "homework_not_completed", "severity": "medium", "therapist_copy": THERAPIST_RETENTION_NUDGE, "patient_copy": PATIENT_RETENTION_NUDGE})
    if onboarding and onboarding.get("status") == "active":
        completed, total = onboarding_progress(onboarding)
        if completed < max(total - 2, 1):
            retention_alerts.append({"type": "onboarding_incomplete", "severity": "low", "therapist_copy": THERAPIST_RETENTION_NUDGE, "patient_copy": PATIENT_RETENTION_NUDGE})

    return {
        "baseline": baseline,
        "current_snapshot": current_snapshot,
        "progress_markers": progress_markers[:5],
        "setback_markers": setback_markers[:5],
        "recurring_triggers": recurring_triggers,
        "helpful_strategies": helpful_strategies[:5],
        "homework_impact": homework_impact,
        "timeline_events": timeline_events,
        "next_session_points": next_session_points[:5],
        "retention_message": (
            "Il percorso può avere fasi di miglioramento e momenti di fatica. "
            "L'obiettivo è capire cosa succede e quali strategie aiutano a recuperare."
        ),
        "disclaimer": NON_DIAGNOSTIC_DISCLAIMER,
        "retention_alerts": retention_alerts,
    }
