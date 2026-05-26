from services.progress_journey_service import build_progress_journey_summary


def _wellness(entries=None, assignments=None, submissions=None, onboardings=None):
    return {
        "mood_entries": entries or [],
        "homework_assignments": assignments or [],
        "homework_submissions": submissions or [],
        "post_consultation_onboardings": onboardings or [],
    }


def test_empty_data_returns_safe_empty_summary():
    res = build_progress_journey_summary({})
    assert isinstance(res, dict)
    assert res["baseline"]["source"] in {"mood_entries", "post_consultation_onboarding"}


def test_baseline_extracted_from_onboarding():
    w = _wellness(onboardings=[{"status": "active", "steps": {"baseline": {"data": {"mood": 3, "stress": 8}}}}])
    res = build_progress_journey_summary(w)
    assert res["baseline"]["mood"] == 3


def test_current_snapshot_uses_recent_entries_and_progress_or_setback():
    entries = [
        {"data": "2026-05-15", "ansia": 8, "stress": 8, "umore_intensita": 3, "trigger": "lavoro"},
        {"data": "2026-05-20", "ansia": 4, "stress": 4, "umore_intensita": 6, "trigger": "lavoro"},
        {"data": "2026-05-24", "ansia": 3, "stress": 4, "umore_intensita": 7, "trigger": "sonno"},
    ]
    res = build_progress_journey_summary(_wellness(entries=entries))
    assert res["current_snapshot"]["recent_anxiety_avg"] is not None
    assert any("miglioramento" in m.lower() for m in res["progress_markers"]) or any("difficoltà" in m.lower() for m in res["setback_markers"])


def test_recurring_triggers_and_homework_helpful_strategies_and_chronological_timeline():
    entries = [{"data": "2026-05-20", "ansia": 6, "stress": 5, "umore_intensita": 5, "trigger": "lavoro, sonno"}]
    assignments = [{"id": "a1", "template": "Nota per la seduta", "assigned_at": "2026-05-19"}]
    submissions = [{"assignment_id": "a1", "submitted_at": "2026-05-21"}]
    res = build_progress_journey_summary(_wellness(entries=entries, assignments=assignments, submissions=submissions))
    assert res["recurring_triggers"][0]["count"] >= 1
    assert res["helpful_strategies"]
    dates = [str(x.get("date") or "") for x in res["timeline_events"]]
    assert dates == sorted(dates)


def test_next_session_points_disclaimer_no_diagnostic_language_missing_fields_and_retention_alerts():
    w = _wellness(
        entries=[{"data": "2026-05-01"}],
        assignments=[{"id": "a1", "template": "Nota"}],
        submissions=[],
        onboardings=[{"status": "active", "steps": {"baseline": {"data": {}}}}],
    )
    res = build_progress_journey_summary(w)
    assert res["next_session_points"]
    assert "diagnosi" not in " ".join(res["progress_markers"] + res["setback_markers"]).lower()
    assert "diagnosi" in res["disclaimer"].lower()
    assert res["retention_alerts"]
