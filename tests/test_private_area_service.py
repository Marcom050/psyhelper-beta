from services.private_area_service import (
    create_private_entry,
    list_patient_private_entries,
    list_shared_entries_for_therapist,
    revoke_shared_entry,
    share_private_entry,
    update_private_entry,
)
from services.report_service import build_pre_session_summary, build_timeline_events, clinical_snapshot, weekly_recap


def test_new_private_area_entry_is_private_by_default():
    wellness = {}

    entry = create_private_entry(wellness, "Cose che vorrei dire", "Materiale da portare in seduta")

    assert entry["share_status"] == "private"
    assert entry["shared_at"] is None
    assert entry["revoked_at"] is None
    assert entry["source"] == "patient_private_area"
    assert wellness["private_area_entries"][0]["id"] == entry["id"]


def test_therapist_does_not_see_private_entries():
    wellness = {}
    create_private_entry(wellness, "Privata", "Non ancora condivisa")

    assert list_patient_private_entries(wellness)
    assert list_shared_entries_for_therapist(wellness) == []


def test_therapist_sees_entry_after_share():
    wellness = {}
    entry = create_private_entry(wellness, "Pronta", "Può essere letta")

    share_private_entry(wellness, entry["id"])

    shared_entries = list_shared_entries_for_therapist(wellness)
    assert len(shared_entries) == 1
    assert shared_entries[0]["title"] == "Pronta"
    assert shared_entries[0]["share_status"] == "shared"
    assert shared_entries[0]["shared_at"] is not None


def test_revoked_entry_is_hidden_from_therapist_normal_views():
    wellness = {}
    entry = create_private_entry(wellness, "Da revocare", "Testo condiviso")
    share_private_entry(wellness, entry["id"])

    revoked = revoke_shared_entry(wellness, entry["id"])

    assert revoked["share_status"] == "revoked"
    assert revoked["revoked_at"] is not None
    assert list_shared_entries_for_therapist(wellness) == []


def test_only_private_entries_can_be_edited():
    wellness = {}
    entry = create_private_entry(wellness, "Bozza", "Testo")

    updated = update_private_entry(wellness, entry["id"], "Bozza aggiornata", "Nuovo testo")
    share_private_entry(wellness, entry["id"])
    blocked = update_private_entry(wellness, entry["id"], "Non deve", "Cambiare")

    assert updated["title"] == "Bozza aggiornata"
    assert blocked is None
    assert list_shared_entries_for_therapist(wellness)[0]["title"] == "Bozza aggiornata"


def test_private_entries_do_not_enter_timeline_report_or_weekly_recap():
    wellness = {}
    create_private_entry(wellness, "Privata", "suicidio lavoro sociale evitare disastro")

    events = build_timeline_events(wellness)
    report = clinical_snapshot(wellness, messages=[])
    recap = weekly_recap(report)

    assert events == []
    assert "Privata" not in report.export_text
    assert "suicidio" not in " ".join(report.alerts).lower()
    assert "Privata" not in recap.to_text()


def test_shared_entries_are_available_in_pre_session_separate_section_only():
    wellness = {}
    private_entry = create_private_entry(wellness, "Ancora privata", "Non mostrare")
    shared_entry = create_private_entry(wellness, "Cose che vorrei dire", "Puoi condividerlo quando ti senti pronto/a")
    revoked_entry = create_private_entry(wellness, "Revocata", "Non più visibile")
    share_private_entry(wellness, shared_entry["id"])
    share_private_entry(wellness, revoked_entry["id"])
    revoke_shared_entry(wellness, revoked_entry["id"])

    summary = build_pre_session_summary(wellness)

    shared = summary["private_area_shared_entries"]
    assert [entry["title"] for entry in shared] == ["Cose che vorrei dire"]
    assert private_entry["title"] not in str(summary["discussion_points"])
    assert shared_entry["title"] not in str(summary["discussion_points"])
    assert revoked_entry["title"] not in str(shared)
