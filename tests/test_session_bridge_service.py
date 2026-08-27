from copy import deepcopy
from datetime import datetime, timezone

import pytest

from services.session_bridge_service import (
    RecencyPolicy,
    SessionBridgeValidationError,
    build_bridge_candidates,
    build_bridge_preview,
    source_reference,
    transition_session_bridge,
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


def test_legacy_references_are_deterministic_namespaced_and_not_position_dependent():
    item = {"title": "Legacy", "content": "same"}
    first = source_reference("journey_goal", item, legacy_index=0)
    assert first == source_reference("journey_goal", deepcopy(item), legacy_index=0)
    assert first.startswith("session_bridge:journey_goal:legacy:")
    assert first == source_reference("journey_goal", item, legacy_index=1)


def test_reordering_identifiable_legacy_records_does_not_change_references():
    first = {"assignment_id": "hw-a", "submitted_at": "2026-08-10T00:00:00Z", "summary": "A"}
    second = {"assignment_id": "hw-b", "submitted_at": "2026-08-11T00:00:00Z", "summary": "B"}
    wellness = {"homework_submissions": [first, second]}
    before = {item["ref"] for item in build_bridge_candidates(wellness, now=NOW)}
    wellness["homework_submissions"].reverse()
    after = {item["ref"] for item in build_bridge_candidates(wellness, now=NOW)}
    assert before == after


def test_exact_duplicate_legacy_records_are_explicitly_collapsed():
    duplicate = {"submitted_at": "2026-08-10T00:00:00Z", "template": "Nota", "summary": "Uguale"}
    candidates = build_bridge_candidates({"homework_submissions": [duplicate, deepcopy(duplicate)]}, now=NOW)
    assert len(candidates) == 1


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


def test_selected_items_do_not_require_a_priority():
    ref = "session_bridge:diary_entry:id:entry-1"
    payload = validate_bridge_payload({"selected_refs": [ref], "priority_ref": None})

    assert payload.selected_refs == (ref,)
    assert payload.priority_ref is None


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


def test_preview_marks_no_item_as_priority_when_priority_is_null():
    wellness = sample_wellness()
    selected = [item["ref"] for item in build_bridge_candidates(wellness, now=NOW)[:2]]

    preview = build_bridge_preview(wellness, {"selected_refs": selected, "priority_ref": None}, now=NOW)

    assert preview["priority_ref"] is None
    assert not any(item["is_priority"] for item in preview["items"])


def test_selected_item_remains_resolvable_after_recency_window_but_is_not_proposed():
    wellness = sample_wellness()
    ref = next(item["ref"] for item in build_bridge_candidates(wellness, now=NOW) if item["source_type"] == "homework_submission")
    later = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
    assert ref not in {item["ref"] for item in build_bridge_candidates(wellness, now=later)}
    preview = build_bridge_preview(wellness, {"selected_refs": [ref], "priority_ref": ref}, now=later)
    assert preview["items"][0]["ref"] == ref
    assert preview["unavailable_refs"] == []


def test_deleted_item_does_not_break_remaining_preview_and_invalid_priority_is_cleared():
    wellness = sample_wellness()
    candidates = build_bridge_candidates(wellness, now=NOW)
    refs = [candidates[0]["ref"], candidates[2]["ref"]]
    wellness["homework_submissions"].pop(0)
    preview = build_bridge_preview(wellness, {"selected_refs": refs, "priority_ref": refs[1]}, now=NOW)
    assert [item["ref"] for item in preview["items"]] == [refs[0]]
    assert preview["priority_ref"] is None
    assert preview["unavailable_refs"] == [{"ref": refs[1], "reason": "source_unavailable"}]
    assert all(item["is_priority"] is False for item in preview["items"])


def test_revoked_note_is_not_shown_and_is_reported_unavailable():
    wellness = sample_wellness()
    ref = next(item["ref"] for item in build_bridge_candidates(wellness, now=NOW) if item["source_type"] == "shared_private_area")
    wellness["private_area_entries"][0]["share_status"] = "revoked"
    preview = build_bridge_preview(wellness, {"selected_refs": [ref], "priority_ref": ref}, now=NOW)
    assert preview["items"] == []
    assert preview["priority_ref"] is None
    assert preview["unavailable_refs"] == [{"ref": ref, "reason": "revoked"}]


def test_active_goals_and_next_session_items_do_not_age_out():
    wellness = sample_wellness()
    much_later = datetime(2030, 1, 1, tzinfo=timezone.utc)
    types = {item["source_type"] for item in build_bridge_candidates(wellness, now=much_later)}
    assert "journey_goal" in types
    assert "next_session" in types


def test_bridge_lifecycle_is_role_scoped_idempotent_and_keeps_material():
    wellness = sample_wellness()
    ref = build_bridge_candidates(wellness, now=NOW)[0]["ref"]
    original = {"selected_refs": [ref], "priority_ref": ref, "optional_text": "Parliamone", "week_rating": 3}
    wellness["session_bridge"] = original.copy()

    ready = transition_session_bridge(wellness, "ready", actor_role="client", now=NOW)
    assert ready["status"] == "ready"
    assert ready["selected_refs"] == [ref]
    assert transition_session_bridge(wellness, "ready", actor_role="client", now=NOW) == ready

    reviewed = transition_session_bridge(wellness, "review", actor_role="therapist", now=NOW)
    archived = transition_session_bridge(wellness, "archive", actor_role="therapist", now=NOW)
    assert reviewed["status"] == "reviewed"
    assert archived["status"] == "archived"
    assert archived["selected_refs"] == original["selected_refs"]
    assert archived["optional_text"] == original["optional_text"]


def test_bridge_lifecycle_rejects_private_draft_and_wrong_role():
    wellness = {"session_bridge": {"selected_refs": [], "priority_ref": None, "optional_text": "", "week_rating": 4}}
    with pytest.raises(SessionBridgeValidationError):
        transition_session_bridge(wellness, "ready", actor_role="client", now=NOW)

    wellness["session_bridge"]["optional_text"] = "Da condividere"
    with pytest.raises(SessionBridgeValidationError):
        transition_session_bridge(wellness, "review", actor_role="therapist", now=NOW)


def test_optional_text_only_bridge_remains_readable_after_submission():
    wellness = {"session_bridge": {"selected_refs": [], "priority_ref": None,
                                   "optional_text": "Un pensiero", "week_rating": None}}
    ready = transition_session_bridge(wellness, "ready", actor_role="client", now=NOW)
    assert ready["status"] == "ready"
    assert validate_bridge_payload(ready).optional_text == "Un pensiero"
