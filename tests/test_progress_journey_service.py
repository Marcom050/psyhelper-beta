from services.progress_journey_service import build_progress_journey_summary


def _wellness(entries=None, assignments=None, submissions=None, onboardings=None):
    return {
        "mood_entries": entries or [],
        "homework_assignments": assignments or [],
        "homework_submissions": submissions or [],
        "post_consultation_onboardings": onboardings or [],
    }


def test_timeline_events_have_stable_shape():
    res = build_progress_journey_summary(_wellness())
    event = res["timeline_events"][0]
    required_keys = {"date", "date_label", "type", "title", "description", "source", "non_diagnostic"}
    assert required_keys.issubset(set(event.keys()))


def test_timeline_events_are_chronological():
    entries = [
        {"data": "2026-05-10", "ansia": 8, "stress": 8, "umore_intensita": 2},
        {"data": "2026-05-20", "ansia": 4, "stress": 4, "umore_intensita": 6},
    ]
    res = build_progress_journey_summary(_wellness(entries=entries))
    dates = [str(event.get("date") or "") for event in res["timeline_events"]]
    assert dates == sorted(dates)


def test_timeline_includes_baseline_event_when_available():
    onboardings = [{"status": "completed", "started_at": "2026-05-01", "steps": {"baseline": {"data": {"stress": 7}}}}]
    res = build_progress_journey_summary(_wellness(onboardings=onboardings))
    assert any(event["type"] == "baseline" for event in res["timeline_events"])


def test_timeline_includes_homework_event_when_available():
    assignments = [{"id": "a1", "template": "Respiro", "assigned_at": "2026-05-03"}]
    submissions = [{"assignment_id": "a1", "submitted_at": "2026-05-05"}]
    res = build_progress_journey_summary(_wellness(assignments=assignments, submissions=submissions))
    assert any(event["type"] == "homework" for event in res["timeline_events"])


def test_timeline_includes_setback_event_when_stress_or_anxiety_increase():
    entries = [
        {"data": "2026-05-14", "ansia": 3, "stress": 3, "umore_intensita": 6},
        {"data": "2026-05-24", "ansia": 8, "stress": 8, "umore_intensita": 3},
    ]
    res = build_progress_journey_summary(_wellness(entries=entries))
    assert any(event["type"] == "setback" for event in res["timeline_events"])


def test_timeline_includes_progress_event_when_stress_or_anxiety_decrease():
    entries = [
        {"data": "2026-05-14", "ansia": 8, "stress": 8, "umore_intensita": 2},
        {"data": "2026-05-24", "ansia": 3, "stress": 3, "umore_intensita": 7},
    ]
    res = build_progress_journey_summary(_wellness(entries=entries))
    assert any(event["type"] == "progress" for event in res["timeline_events"])


def test_missing_date_does_not_crash():
    assignments = [{"id": "a1", "template": "Compito senza data"}]
    submissions = [{"assignment_id": "a1"}]
    res = build_progress_journey_summary(_wellness(assignments=assignments, submissions=submissions))
    assert res["timeline_events"]
    assert any(event["date_label"] == "Data non disponibile" for event in res["timeline_events"])


def test_no_diagnostic_language_in_timeline_labels():
    res = build_progress_journey_summary(_wellness())
    timeline_text = " ".join(
        f"{event.get('title', '')} {event.get('description', '')}" for event in res["timeline_events"]
    ).lower()
    assert "diagnosi" not in timeline_text
    assert "disturbo" not in timeline_text
