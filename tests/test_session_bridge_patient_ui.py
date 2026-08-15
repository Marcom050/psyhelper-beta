from datetime import datetime, timezone
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


def test_patient_tabs_keep_the_six_existing_sections_in_order_without_bridge():
    expected = ["💬 Chat", "📝 Diario CBT", "🔐 Area privata", "📚 Homework CBT", "📈 Monitoraggio", "📋 Resoconto"]
    tab_contexts = [Mock() for _ in expected]
    for context in tab_contexts:
        context.__enter__ = Mock(return_value=context)
        context.__exit__ = Mock(return_value=False)

    with patch.object(app.st, "tabs", return_value=tab_contexts) as tabs, \
            patch.object(app, "show_chat_tab"), patch.object(app, "show_diary_tab"), \
            patch.object(app, "show_private_area_tab"), patch.object(app, "show_homework_tab"), \
            patch.object(app, "show_monitoring_tab"), patch.object(app, "show_report_tab"):
        app.render_client_app_tabs()

    tabs.assert_called_once_with(expected)
    assert "Per la prossima seduta" not in tabs.call_args.args[0]


def test_patient_dashboard_shows_cta_and_cta_opens_dedicated_bridge_view():
    ui_state = {}
    adapter = Mock()
    adapter.get_ui_state.side_effect = lambda key, default=None: ui_state.get(key, default)
    adapter.set_ui_state.side_effect = lambda key, value: ui_state.__setitem__(key, value)

    with patch.object(app, "session_adapter", adapter), \
            patch.object(app.st, "button", return_value=True) as button, \
            patch.object(app.st, "rerun") as rerun, \
            patch.object(app, "render_client_app_tabs") as tabs, \
            patch.object(app, "show_session_bridge_tab") as bridge:
        app.render_client_navigation()

    button.assert_called_once_with("Prepara la prossima seduta", key="session_bridge_open", type="primary")
    assert ui_state[app.SESSION_BRIDGE_VIEW_KEY] is True
    rerun.assert_called_once_with()
    tabs.assert_not_called()
    bridge.assert_not_called()


def test_bridge_back_returns_to_dashboard_without_losing_draft_or_saving():
    draft_key = "session_bridge_draft:patient"
    draft = {"selected_refs": ["diary:1"], "priority_ref": "diary:1", "optional_text": "Bozza", "week_rating": 4}
    ui_state = {app.SESSION_BRIDGE_VIEW_KEY: True, draft_key: draft.copy()}
    adapter = Mock()
    adapter.get_ui_state.side_effect = lambda key, default=None: ui_state.get(key, default)
    adapter.set_ui_state.side_effect = lambda key, value: ui_state.__setitem__(key, value)

    with patch.object(app, "session_adapter", adapter), \
            patch.object(app.st, "button", return_value=True) as button, \
            patch.object(app.st, "rerun") as rerun, \
            patch.object(app, "render_client_app_tabs") as tabs, \
            patch.object(app, "show_session_bridge_tab") as bridge, \
            patch.object(app, "save_session_bridge_for") as save:
        app.render_client_navigation()

    button.assert_called_once_with("← Torna al percorso", key="session_bridge_back_to_dashboard")
    assert ui_state[app.SESSION_BRIDGE_VIEW_KEY] is False
    assert ui_state[draft_key] == draft
    rerun.assert_called_once_with()
    tabs.assert_not_called()
    bridge.assert_not_called()
    save.assert_not_called()


def test_bridge_view_is_dedicated_and_entry_does_not_save():
    adapter = Mock()
    adapter.get_ui_state.return_value = True

    with patch.object(app, "session_adapter", adapter), \
            patch.object(app.st, "button", return_value=False), \
            patch.object(app, "render_client_app_tabs") as tabs, \
            patch.object(app, "show_session_bridge_tab") as bridge, \
            patch.object(app, "save_session_bridge_for") as save:
        app.render_client_navigation()

    bridge.assert_called_once_with()
    tabs.assert_not_called()
    save.assert_not_called()


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


def test_compact_bridge_hides_technical_headings_and_empty_preview():
    ui_state = {}
    adapter = Mock()
    adapter.get_username.return_value = "patient"
    adapter.get_wellness.return_value = bridge_wellness()
    adapter.has_ui_state.side_effect = lambda key: key in ui_state
    adapter.get_ui_state.side_effect = lambda key, default=None: ui_state.get(key, default)
    adapter.set_ui_state.side_effect = lambda key, value: ui_state.__setitem__(key, value)

    with patch.object(app, "session_adapter", adapter), \
            patch.object(app, "load_session_bridge_for", return_value=empty_session_bridge()), \
            patch.object(app, "session_bridge_candidates_for_ui", return_value={
                "diary_entry": [], "homework_submission": [],
            }), patch.object(app.st, "radio", return_value=None), \
            patch.object(app.st, "text_area", return_value="") as text_area, \
            patch.object(app.st, "button", return_value=False), \
            patch.object(app.st, "subheader") as subheader, \
            patch.object(app.st, "markdown") as markdown:
        app.show_session_bridge_tab()

    headings = [call.args[0] for call in subheader.call_args_list]
    assert headings == ["Dal tuo diario", "Attività completate"]
    assert "Settimana" not in headings
    assert "Testo libero" not in headings
    assert "Per la prossima seduta" not in headings
    markdown.assert_any_call(
        "#### C'è qualcos'altro che vuoi portare con te? "
        '<span style="color:#6b7280;font-size:.78rem;font-weight:400">Facoltativo</span>',
        unsafe_allow_html=True,
    )
    text_area.assert_called_once_with(
        "C'è qualcos'altro che vuoi portare con te?",
        max_chars=app.DEFAULT_TEXT_MAX_LENGTH,
        key="session_bridge_optional_text:patient",
        label_visibility="collapsed",
        height=68,
    )


def test_compact_bridge_shows_preview_when_optional_text_has_content():
    draft = {**empty_session_bridge(), "optional_text": "Un pensiero da portare"}
    adapter = Mock()
    adapter.get_username.return_value = "patient"
    adapter.get_wellness.return_value = bridge_wellness()
    adapter.has_ui_state.return_value = True
    adapter.get_ui_state.side_effect = lambda key, default=None: draft

    with patch.object(app, "session_adapter", adapter), \
            patch.object(app, "load_session_bridge_for", return_value=draft), \
            patch.object(app, "session_bridge_candidates_for_ui", return_value={
                "diary_entry": [], "homework_submission": [],
            }), patch.object(app.st, "radio", return_value=None), \
            patch.object(app.st, "text_area", return_value=draft["optional_text"]), \
            patch.object(app.st, "button", return_value=False), \
            patch.object(app.st, "subheader") as subheader:
        app.show_session_bridge_tab()

    assert "Per la prossima seduta" in [call.args[0] for call in subheader.call_args_list]


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
