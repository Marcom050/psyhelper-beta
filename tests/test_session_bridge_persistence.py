import json

import pytest

from database.wellness_repository import load_wellness, save_wellness
from services.session_bridge_service import (
    SessionBridgeValidationError,
    get_session_bridge,
    save_session_bridge,
)


EMPTY = {"selected_refs": [], "priority_ref": None, "optional_text": ""}
REF = "session_bridge:journey_goal:id:goal-1"


def test_legacy_document_reads_as_empty_without_mutation():
    wellness = {"mood_entries": [], "unknown_extension": {"kept": True}}

    assert get_session_bridge(wellness) == EMPTY
    assert "session_bridge" not in wellness


def test_save_replaces_only_bridge_and_preserves_unknown_wellness_keys():
    wellness = {"mood_entries": [{"id": "m1"}], "unknown_extension": [1, 2]}
    payload = {"selected_refs": [REF], "priority_ref": REF, "optional_text": "Da ricordare"}

    assert save_session_bridge(wellness, payload) == payload
    assert wellness == {"mood_entries": [{"id": "m1"}], "unknown_extension": [1, 2], "session_bridge": payload}
    assert get_session_bridge(wellness) == payload


@pytest.mark.parametrize("payload", [
    {"selected_refs": [REF, REF], "priority_ref": REF, "optional_text": ""},
    {"selected_refs": [REF], "priority_ref": "session_bridge:journey_goal:id:other", "optional_text": ""},
])
def test_save_uses_bridge_domain_validation(payload):
    with pytest.raises(SessionBridgeValidationError):
        save_session_bridge({}, payload)


def test_filesystem_round_trip_preserves_bridge_and_other_keys(tmp_path):
    wellness = {"mood_entries": [], "unknown_extension": "value"}
    payload = {"selected_refs": [REF], "priority_ref": REF, "optional_text": "Nota"}
    save_session_bridge(wellness, payload)

    save_wellness(str(tmp_path), wellness)
    loaded = load_wellness(str(tmp_path))

    assert get_session_bridge(loaded) == payload
    assert loaded["unknown_extension"] == "value"
    assert json.loads((tmp_path / "wellness.json").read_text())["session_bridge"] == payload
