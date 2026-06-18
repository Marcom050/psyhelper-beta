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
        "progress": "improvement",
        "homework_completed": "homework",
        "homework assegnato": "homework",
        "homework completato": "homework",
        "start": "onboarding",
        "evento clinico": "note",
    }
    normalized_type = type_aliases.get(raw_type, raw_type)
    allowed_types = {
        "baseline", "improvement", "setback", "attention_area", "step_forward",
        "maintained_progress", "homework", "onboarding", "note", "session", "trigger",
    }
    if normalized_type not in allowed_types:
        normalized_type = "note"
    title = event.get("title") or event.get("titolo") or "Evento del percorso"
    description = event.get("description") or event.get("dettaglio") or ""
    source = event.get("source") or "progress_journey"
    non_diagnostic = bool(event.get("non_diagnostic", True))
    importance = event.get("importance") or event.get("severity") or event.get("evidence_level") or "low"
    evidence = event.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    return {
        "date": date_value,
        "date_label": event.get("date_label") or _to_date_label(date_value),
        "type": normalized_type,
        "title": str(title),
        "description": str(description),
        "source": str(source),
        "importance": str(importance),
        "evidence": [str(item) for item in evidence],
        "is_clinical_disclaimer_needed": bool(event.get("is_clinical_disclaimer_needed", True)),
        "non_diagnostic": non_diagnostic,
    }


def _timeline_event(event_type: str, title: str, description: str, date: Any, source: str, *, importance: str = "medium", evidence: Optional[list[str]] = None) -> dict[str, Any]:
    return {
        "date": date,
        "date_label": _to_date_label(date),
        "type": event_type,
        "title": title,
        "description": description,
        "source": source,
        "importance": importance,
        "evidence": evidence or [],
        "is_clinical_disclaimer_needed": True,
        "non_diagnostic": True,
    }


def _split_themes(value: Any) -> list[str]:
    return [part.strip().lower() for part in str(value or "").split(",") if part.strip()]


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

    now = (df["data"].max() if not df.empty else pd.Timestamp.now()).tz_localize(None).normalize()
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
        if delta_anx <= -1 or delta_stress <= -1:
            evidence = [f"ansia: variazione media {delta_anx:.1f}", f"stress: variazione media {delta_stress:.1f}"]
            progress_markers.append("Possibile segnale da esplorare in seduta: nei dati recenti ansia/stress risultano in riduzione rispetto alla settimana precedente.")
            timeline_events.append(_timeline_event("improvement", "Miglioramento osservato", "Negli ultimi check-in si osserva una riduzione di ansia/stress o una maggiore stabilità emotiva. Segnale da discutere in seduta.", now.isoformat(), "mood_entries", evidence=evidence))
        if delta_anx >= 1 or delta_stress >= 1:
            evidence = [f"ansia: variazione media +{delta_anx:.1f}", f"stress: variazione media +{delta_stress:.1f}"]
            setback_markers.append("Possibile ricaduta da esplorare: aumento recente di ansia/stress rispetto alla settimana precedente.")
            timeline_events.append(_timeline_event("setback", "Possibile ricaduta da esplorare", "Negli ultimi check-in ansia o stress risultano aumentati rispetto al periodo precedente. Può essere utile esplorare cosa è cambiato.", now.isoformat(), "mood_entries", importance="high", evidence=evidence))

    recent_rows = recent_14.to_dict("records") if not recent_14.empty else []
    trigger_counter = Counter()
    automatic_thought_counter = Counter()
    behavior_counter = Counter()
    for row in recent_rows:
        trigger_counter.update(_split_themes(row.get("trigger")))
        automatic_thought_counter.update(_split_themes(row.get("pensiero_automatico")))
        behavior_counter.update(_split_themes(row.get("comportamento")))
    recurring_triggers = [{"trigger": k, "count": v} for k, v in trigger_counter.most_common(5)]

    for theme, count in trigger_counter.most_common(3):
        if count >= 2:
            timeline_events.append(_timeline_event("attention_area", f"Area da attenzionare: {theme}", "Questo tema compare più volte nei check-in recenti e potrebbe essere utile riprenderlo in seduta.", now.isoformat(), "mood_entries", evidence=[f"trigger ricorrente: {theme} ({count} volte)"]))
    for theme, count in (automatic_thought_counter + behavior_counter).most_common(3):
        if count >= 2:
            timeline_events.append(_timeline_event("attention_area", f"Area da attenzionare: {theme}", "Questo pensiero o comportamento compare più volte nei check-in recenti: possibile segnale da esplorare in seduta.", now.isoformat(), "mood_entries", evidence=[f"tema ricorrente: {theme} ({count} volte)"]))

    if len(recent_7) >= 2 and not prev_7.empty and recent_7["ansia"].mean() <= prev_7["ansia"].mean() - 1 and recent_7["stress"].mean() <= prev_7["stress"].mean() - 1:
        timeline_events.append(_timeline_event("maintained_progress", "Progresso mantenuto", "Il miglioramento sembra mantenersi nei check-in più recenti. Segnale descrittivo da discutere in seduta.", now.isoformat(), "mood_entries", evidence=["ansia e stress restano più bassi nel periodo recente"]))

    helpful_strategies = []
    homework_impact = []
    for assignment in assignments:
        title = assignment.get("template", "Esercizio")
        aid = assignment.get("id")
        if aid in completed_ids:
            helpful_strategies.append(f"Dopo l'esercizio '{title}', nei dati successivi compaiono informazioni utili da discutere in seduta.")
            homework_impact.append({"homework": title, "status": "completed", "note": "Potrebbe essere utile discuterne in seduta."})
            event_date = assignment.get("assigned_at") or assignment.get("due_date")
            timeline_events.append(_timeline_event("homework", "Homework completato", title, event_date, "homework_submissions", importance="high", evidence=[f"homework completato: {title}"]))
            step_keywords = ["evitamento", "piccolo passo", "esposizione", "paura", "ansia", "situazione evitata"]
            text = f"{title} {assignment.get('instructions', '')}".lower()
            if any(keyword in text for keyword in step_keywords):
                timeline_events.append(_timeline_event("step_forward", "Passo avanti", "È presente un possibile passo avanti: il paziente ha affrontato o descritto un’azione collegata a un blocco precedente.", event_date, "homework_submissions", importance="high", evidence=[f"homework completato collegato a: {title}"]))
        else:
            homework_impact.append({"homework": title, "status": "pending", "note": "Tema da portare in seduta per capire ostacoli e supporti utili."})

    for manual_event in wellness.get("timeline_events", []):
        timeline_events.append({**manual_event, "source": manual_event.get("source") or "manual_timeline"})

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
