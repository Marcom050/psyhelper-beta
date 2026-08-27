from unittest.mock import Mock, patch

import psyhelper_streamlit as app
from services.session_bridge_service import source_reference


def _wellness(status="ready"):
    shared = {"id": "shared", "share_status": "shared", "title": "Scelto", "content": "Condiviso"}
    private = {"id": "private", "share_status": "private", "title": "Privato", "content": "Segreto"}
    ref = source_reference("shared_private_area", shared)
    return {
        "private_area_entries": [shared, private],
        "session_bridge": {
            "selected_refs": [ref], "priority_ref": ref, "optional_text": "Nota scelta", "week_rating": 4,
            "status": status, "ready_at": "2026-08-27T10:00:00+00:00",
        },
    }


def test_therapist_draft_is_not_resolved_or_rendered():
    wellness = _wellness("ready")
    wellness["session_bridge"].pop("ready_at")
    wellness["session_bridge"]["status"] = "draft"
    with patch.object(app, "build_bridge_preview") as preview, patch.object(app.st, "info") as info:
        app.show_therapist_session_bridge("patient", "Nome", wellness)
    preview.assert_not_called()
    assert "preparando" in info.call_args.args[0]


def test_therapist_ready_view_contains_only_resolved_selected_material():
    container = Mock()
    container.__enter__ = Mock(return_value=container)
    container.__exit__ = Mock(return_value=False)
    with patch.object(app.st, "container", return_value=container), \
            patch.object(app.st, "write") as write, patch.object(app.st, "button", return_value=False):
        app.show_therapist_session_bridge("patient", "Nome", _wellness())
    rendered = " ".join(str(call.args[0]) for call in write.call_args_list)
    assert "Condiviso" in rendered
    assert "Nota scelta" in rendered
    assert "Segreto" not in rendered
