from uuid import UUID

import pytest

from database.wellness_repository import default_wellness_data, ensure_wellness_schema
from services.journey_goal_service import (
    EMPTY_BASELINE,
    JourneyGoalError,
    JourneyGoalPermissionError,
    achieved_goals,
    active_goals,
    build_patient_progress_recap,
    build_starting_point,
    create_patient_goal,
    extract_initial_goals,
    materialize_initial_goals,
    normalize_journey_goals,
    update_goal_by_therapist,
)


def test_legacy_wellness_schema_and_empty_state():
    legacy = {"mood_entries": []}
    ensure_wellness_schema(legacy)
    assert legacy["journey_goals"] == []
    assert build_starting_point({}, legacy)["empty_message"] == EMPTY_BASELINE
    assert build_starting_point({}, legacy)["empty"] is True
    assert "journey_goals" in default_wellness_data()


def test_patient_goal_uses_unique_real_uuids_and_blocks_normalized_duplicates():
    wellness = {}
    one = create_patient_goal(wellness, "  Parlare più chiaramente. ")
    two = create_patient_goal(wellness, "Dormire meglio")
    assert UUID(one["id"]) and UUID(two["id"])
    assert one["id"] != two["id"]
    assert one["title"] == "Parlare più chiaramente"
    assert one["status"] == "active" and one["achieved_at"] is None
    with pytest.raises(JourneyGoalError):
        create_patient_goal(wellness, "PARLARE   PIÙ CHIARAMENTE!")


def test_extracts_new_onboarding_legacy_profile_and_timeline_idempotently():
    profile = {"obiettivi": "Ridurre l'evitamento", "initial_baseline": {"goals": ["Esprimermi meglio"]}}
    wellness = {
        "post_consultation_onboardings": [{"steps": {"goals": {"data": {
            "goals_text": "Gestire l'ansia; Dormire meglio",
            "short_term_priority": "Fare un piccolo passo",
            "main_goal": "Gestire l'ansia",
            "track": "Relazioni",
            "personal_commitment": "Compilare il diario",
        }}}}],
        "timeline_events": [{"tipo": "obiettivo", "titolo": "Chiedere aiuto"}],
    }
    extracted = extract_initial_goals(profile, wellness)
    assert {"Ridurre l'evitamento", "Esprimermi meglio", "Gestire l'ansia", "Dormire meglio", "Fare un piccolo passo", "Relazioni", "Chiedere aiuto"} <= set(extracted)
    assert "Compilare il diario" not in extracted
    assert materialize_initial_goals(wellness, profile) is True
    ids = [goal["id"] for goal in wellness["journey_goals"]]
    assert materialize_initial_goals(wellness, profile) is False
    normalize_journey_goals(wellness)
    assert ids == [goal["id"] for goal in wellness["journey_goals"]]
    assert len(ids) == len(set(ids)) == len(extracted)


def test_commitment_is_excluded_from_all_real_onboarding_shapes():
    wellness = {
        "onboarding": {"goals": {"personal_commitment": "Alias legacy"}},
        "post_consultation_onboardings": [
            {"goals": {"personal_commitment": "Forma top-level"}},
            {"steps": {"goals": {"data": {"personal_commitment": "Forma corrente"}}}},
            {"summary": {"goals": {"personal_commitment": "Forma riepilogo"}}},
        ],
    }
    profile = {"goals": ["Forma top-level", "Forma corrente", "Forma riepilogo", "Alias legacy", "Obiettivo vero"]}

    assert extract_initial_goals(profile, wellness) == ["Obiettivo vero"]


def test_materialization_removes_imported_commitment_but_preserves_manual_match():
    commitment = "Compilare il diario ogni sera"
    wellness = {
        "post_consultation_onboardings": [{"goals": {"personal_commitment": commitment}}],
        "journey_goals": [
            {
                "id": "526095d5-fbcd-59c1-bca6-21a8d22196c4",
                "title": commitment,
                "source": "onboarding",
                "created_at": "1970-01-01T00:00:00+00:00",
            },
            {
                "id": "544eb5b5-65ea-4383-a7a7-443ca7bfcc8f",
                "title": commitment,
                "source": "patient_manual",
                "created_at": "2026-08-01T12:00:00+00:00",
            },
        ],
    }

    assert materialize_initial_goals(wellness, {}) is True
    assert [(goal["title"], goal["source"]) for goal in wellness["journey_goals"]] == [
        (commitment, "patient_manual")
    ]
    assert materialize_initial_goals(wellness, {}) is False
    assert len(wellness["journey_goals"]) == 1


def test_owner_can_confirm_persist_note_and_undo_but_others_cannot():
    wellness = {}
    goal = create_patient_goal(wellness, "Affrontare un confronto")
    updated = update_goal_by_therapist(wellness, goal["id"], achieved=True, note="Passo concordato", actor_username="therapist_a", patient_owner="therapist_a")
    assert updated["status"] == "achieved"
    assert updated["achieved_at"] and updated["achieved_by"] == "therapist_a"
    assert updated["therapist_note"] == "Passo concordato"
    assert achieved_goals(wellness)[0] == updated
    with pytest.raises(JourneyGoalPermissionError):
        update_goal_by_therapist(wellness, goal["id"], achieved=False, note="", actor_username="patient", patient_owner="therapist_a", actor_role="client")
    with pytest.raises(JourneyGoalPermissionError):
        update_goal_by_therapist(wellness, goal["id"], achieved=False, note="", actor_username="therapist_b", patient_owner="therapist_a")
    undone = update_goal_by_therapist(wellness, goal["id"], achieved=False, note="correzione", actor_username="therapist_a", patient_owner="therapist_a")
    assert undone["status"] == "active" and undone["achieved_at"] is None and undone["achieved_by"] is None
    assert active_goals(wellness)[0]["therapist_note"] == "correzione"


def test_recap_only_manual_confirmation_is_achieved():
    wellness = {}
    goal = create_patient_goal(wellness, "Uscire di casa")
    journey = {"progress_markers": ["Possibile miglioramento osservato"], "current_snapshot": {"homework_completed": 2}, "timeline_events": [{"type": "step_forward", "description": "Hai descritto un piccolo passo"}]}
    recap = build_patient_progress_recap(wellness, journey)
    assert recap["achieved_goals"] == []
    assert len(recap["automatic_signals"]) == 3
    assert wellness["journey_goals"][0]["status"] == "active"
    update_goal_by_therapist(wellness, goal["id"], achieved=True, note="", actor_username="t", patient_owner="t")
    assert build_patient_progress_recap(wellness, journey)["achieved_goals"][0]["title"] == "Uscire di casa"


def test_starting_point_uses_aliases_without_raw_dicts():
    profile = {"initial_baseline": {"mood": "teso", "anxiety": 7}}
    wellness = {"diary": {"habits_to_change": "evitare telefonate"}, "cbt_entry": {"automatic_thought": "non ce la faccio"}}
    summary = build_starting_point(profile, wellness)
    assert summary["details"] == ["teso", "7", "evitare telefonate", "non ce la faccio"]
    assert all(not isinstance(item, dict) for item in summary["details"])
