from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import psyhelper_streamlit as app
from services.session_bridge_service import empty_session_bridge, source_reference


NOW = datetime(2026, 8, 14, 12, tzinfo=timezone.utc)


def bridge_wellness():
    return {
        "mood_entries": [
            {"id": "diary-1", "data": "2026-08-13T10:00:00Z", "note": "Un pensiero da ricordare"},
        ],
        "homework_submissions": [
            {
                "id": "submission-1", "assignment_id": "assignment-1", "submitted_at": "2026-08-12T10:00:00Z",
                "template": "Registro", "free_note": "Attività svolta",
            },
        ],
        "journey_goals": [{"id": "goal-1", "title": "Fonte esclusa"}],
        "timeline_events": [
            {"id": "timeline-1", "date": "2026-08-13T10:00:00Z", "title": "Fonte esclusa"},
        ],
        "private_area_entries": [
            {"id": "private-1", "share_status": "shared", "title": "Fonte esclusa", "content": "Privato"},
        ],
    }


def test_patient_tab_is_additive_and_keeps_previous_tabs():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    tab_line = next(line for line in source.splitlines() if "app_tabs = st.tabs" in line)
    for previous in ("Chat", "Diario CBT", "Area privata", "Homework CBT", "Monitoraggio", "Resoconto"):
        assert previous in tab_line
    assert "Per la prossima seduta" in tab_line
    assert "show_session_bridge_tab()" in source


def test_empty_and_saved_bridge_load_through_local_boundary():
    wellness = bridge_wellness()
    assert app.load_session_bridge_for("patient", wellness) == empty_session_bridge()
    diary_ref = source_reference("diary_entry", wellness["mood_entries"][0])
    saved = {"selected_refs": [diary_ref], "priority_ref": diary_ref, "optional_text": "Altro", "week_rating": 4}
    wellness["session_bridge"] = saved
    assert app.load_session_bridge_for("patient", wellness) == saved


def test_week_rating_none_and_each_value_are_preserved_by_existing_validation():
    for rating in (None, 1, 2, 3, 4, 5):
        payload = {**empty_session_bridge(), "week_rating": rating}
        assert app.validate_session_bridge_state(payload)["week_rating"] is rating


def test_candidate_selection_removal_and_only_one_priority():
    draft = empty_session_bridge()
    app.update_session_bridge_selection(draft, "ref-1", True)
    app.update_session_bridge_selection(draft, "ref-2", True)
    app.update_session_bridge_priority(draft, "ref-1")
    app.update_session_bridge_priority(draft, "ref-2")
    assert draft["priority_ref"] == "ref-2"
    app.update_session_bridge_selection(draft, "ref-2", False)
    assert draft == {"selected_refs": ["ref-1"], "priority_ref": None, "optional_text": "", "week_rating": None}


def test_optional_text_preview_save_and_unavailable_item():
    wellness = bridge_wellness()
    ref = source_reference("diary_entry", wellness["mood_entries"][0])
    draft = {"selected_refs": [ref], "priority_ref": ref, "optional_text": "Da ricordare", "week_rating": 1}
    preview = app._session_bridge_draft_preview(wellness, draft)
    assert preview["items"][0]["ref"] == ref
    assert preview["optional_text"] == "Da ricordare"

    wellness["mood_entries"].clear()
    unavailable = app._session_bridge_draft_preview(wellness, draft)
    assert unavailable["items"] == []
    assert unavailable["unavailable_refs"] == [{"ref": ref, "reason": "source_unavailable"}]


def test_ui_preview_and_save_allow_selected_item_without_priority():
    wellness = bridge_wellness()
    ref = source_reference("diary_entry", wellness["mood_entries"][0])
    draft = {"selected_refs": [ref], "priority_ref": None, "optional_text": "", "week_rating": None}

    preview = app._session_bridge_draft_preview(wellness, draft)

    assert preview["priority_ref"] is None
    assert preview["items"][0]["is_priority"] is False


def test_ui_candidate_subset_contains_only_recent_diary_and_completed_submissions():
    visible = app.session_bridge_candidates_for_ui(bridge_wellness(), now=NOW)
    assert set(visible) == {"diary_entry", "homework_submission"}
    assert {item["source_type"] for items in visible.values() for item in items} == {
        "diary_entry", "homework_submission",
    }
    assert all(len(items) <= app.SESSION_BRIDGE_CANDIDATES_PER_SECTION for items in visible.values())


def test_local_and_http_save_have_equivalent_result_and_update_session_wellness():
    local_wellness = bridge_wellness()
    ref = source_reference("diary_entry", local_wellness["mood_entries"][0])
    payload = {"selected_refs": [ref], "priority_ref": None, "optional_text": "Promemoria", "week_rating": 5}
    with patch.object(app, "use_http_api", return_value=False), patch.object(app, "save_user_data") as persist:
        local = app.save_session_bridge_for("patient", local_wellness, payload)
    persist.assert_called_once_with("patient")

    http_wellness = bridge_wellness()
    client = Mock()
    client.save_session_bridge.return_value = payload.copy()
    with patch.object(app, "use_http_api", return_value=True), patch.object(app, "api_client", return_value=client):
        http = app.save_session_bridge_for("patient", http_wellness, payload)
    assert local == http == payload
    assert local_wellness["session_bridge"] == http_wellness["session_bridge"] == payload
    client.save_session_bridge.assert_called_once_with("patient", payload)


def test_http_load_uses_session_bridge_endpoint_client_method():
    expected = {**empty_session_bridge(), "optional_text": "Già salvato"}
    client = Mock()
    client.get_session_bridge.return_value = expected
    with patch.object(app, "use_http_api", return_value=True), patch.object(app, "api_client", return_value=client):
        assert app.load_session_bridge_for("patient", bridge_wellness()) == expected
    client.get_session_bridge.assert_called_once_with("patient")
