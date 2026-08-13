from copy import deepcopy
from datetime import datetime, timezone

import pytest

from services.session_bridge_service import (
    RecencyPolicy,
    SessionBridgeReferenceError,
    SessionBridgeValidationError,
    build_bridge_candidates,
    build_bridge_preview,
    source_reference,
    validate_bridge_payload,
)


NOW = datetime(2026, 8, 13, 12, tzinfo=timezone.utc)


def sample_wellness():
    return {
        "post_consultation_onboardings": [{
            "id": "onb-1", "created_at": "2026-08-01T10:00:00+00:00",
            "steps": {"next_session_note": {"data": {"points_to_resume": "Riprendere questo punto"}}},
        }],
        "private_area_entries": [
            {"id": "shared", "title": "Condivisa", "content": "Testo", "share_status": "shared", "shared_at": "2026-08-10T00:00:00Z"},
            {"id": "private", "title": "Privata", "content": "Segreta", "share_status": "private"},
            {"id": "revoked", "title": "Revocata", "content": "Segreta", "share_status": "revoked", "revoked_at": "2026-08-11T00:00:00Z"},
            {"id": "therapist", "title": "Nota terapeuta", "content": "Mai", "share_status": "shared", "created_by": "therapist"},
        ],
        "homework_submissions": [
            {"assignment_id": "hw-1", "template": "Nota", "submitted_at": "2026-08-10T00:00:00Z", "answers": {"p": "risposta"}, "summary": "Sintesi"},
            {"assignment_id": "old", "template": "Vecchio", "submitted_at": "2026-01-01T00:00:00Z", "summary": "Fuori finestra"},
        ],
        "mood_entries": [{"data": "2026-08-12", "umore": "Teso", "pensiero_automatico": "Un pensiero"}],
        "journey_goals": [{"id": "goal-1", "title": "Dormire meglio", "therapist_note": "non esporre"}],
        "timeline_events": [{"data": "2026-08-09", "titolo": "Passo", "dettaglio": "Sintesi derivata"}],
    }


def test_candidates_are_pure_unselected_ranked_and_privacy_safe():
    wellness = sample_wellness()
    original = deepcopy(wellness)

    candidates = build_bridge_candidates(wellness, now=NOW)

    assert wellness == original
    assert all(candidate["selected"] is False for candidate in candidates)
    assert [item["source_type"] for item in candidates] == [
        "next_session", "shared_private_area", "homework_submission",
        "diary_entry", "journey_goal", "timeline_summary",
    ]
    combined = repr(candidates)
    assert "Segreta" not in combined
    assert "Nota terapeuta" not in combined
    assert "non esporre" not in combined


def test_recency_policy_is_explicit_and_configurable():
    candidates = build_bridge_candidates(
        sample_wellness(), policy=RecencyPolicy(homework_days=300, diary_days=0, timeline_days=0), now=NOW
    )
    homework_titles = [item["title"] for item in candidates if item["source_type"] == "homework_submission"]
    assert homework_titles == ["Nota", "Vecchio"]
    assert not any(item["source_type"] == "diary_entry" for item in candidates)


def test_legacy_references_are_deterministic_namespaced_and_distinct_by_position():
    item = {"title": "Legacy", "content": "same"}
    first = source_reference("journey_goal", item, legacy_index=0)
    assert first == source_reference("journey_goal", deepcopy(item), legacy_index=0)
    assert first.startswith("session_bridge:journey_goal:legacy:")
    assert first != source_reference("journey_goal", item, legacy_index=1)


@pytest.mark.parametrize("payload,message", [
    ({"selected_refs": ["session_bridge:journey_goal:id:a"] * 2, "priority_ref": "session_bridge:journey_goal:id:a"}, "Duplicate"),
    ({"selected_refs": [f"session_bridge:journey_goal:id:{n}" for n in range(6)], "priority_ref": "session_bridge:journey_goal:id:0"}, "At most"),
    ({"selected_refs": ["session_bridge:journey_goal:id:a"], "priority_ref": ""}, "priority"),
    ({"selected_refs": ["session_bridge:journey_goal:id:a"], "priority_ref": "session_bridge:journey_goal:id:b"}, "priority"),
    ({"selected_refs": ["session_bridge:unknown:id:a"], "priority_ref": "session_bridge:unknown:id:a"}, "Unsupported"),
    ({"selected_refs": ["session_bridge:journey_goal:id:a"], "priority_ref": "session_bridge:journey_goal:id:a", "optional_text": "x" * 501}, "500"),
])
def test_payload_validation_rules(payload, message):
    with pytest.raises(SessionBridgeValidationError, match=message):
        validate_bridge_payload(payload)


def test_preview_resolves_current_source_content_without_copying_it_into_payload():
    wellness = sample_wellness()
    candidates = build_bridge_candidates(wellness, now=NOW)
    selected = [item["ref"] for item in candidates[:2]]
    payload = {"selected_refs": selected, "priority_ref": selected[1], "optional_text": "Nota opzionale"}

    preview = build_bridge_preview(wellness, payload, now=NOW)

    assert set(payload) == {"selected_refs", "priority_ref", "optional_text"}
    assert [item["is_priority"] for item in preview["items"]] == [False, True]
    assert preview["items"][1]["content"] == "Testo"

    wellness["private_area_entries"][0]["content"] = "Testo aggiornato"
    assert build_bridge_preview(wellness, payload, now=NOW)["items"][1]["content"] == "Testo aggiornato"


def test_preview_rejects_reference_that_is_missing_or_no_longer_shareable():
    wellness = sample_wellness()
    ref = next(item["ref"] for item in build_bridge_candidates(wellness, now=NOW) if item["source_type"] == "shared_private_area")
    wellness["private_area_entries"][0]["share_status"] = "revoked"
    with pytest.raises(SessionBridgeReferenceError, match="Unresolvable"):
        build_bridge_preview(wellness, {"selected_refs": [ref], "priority_ref": ref}, now=NOW)
