import unittest

from domain.clinical_model import (
    CHAT_STATUSES,
    CLIENT_STATUSES,
    HOMEWORK_STATUSES,
    REPORT_STATUSES,
    clinical_meta,
    extract_structured_analytics_rows,
    normalized_homework_status,
)


class ClinicalDataFoundationTest(unittest.TestCase):
    def test_client_lifecycle_model(self):
        meta = clinical_meta("client_1", "tenant_a", "client_1", "active", CLIENT_STATUSES, "active")
        self.assertEqual(meta.tenant_id, "tenant_a")
        self.assertEqual(meta.lifecycle_status, "active")

    def test_homework_status_transitions(self):
        assignment = {"id": "hw_1", "status": "assigned", "due_date": "2026-05-10"}
        self.assertEqual(normalized_homework_status(assignment, {"hw_1"}, today_iso="2026-05-12"), "submitted")
        self.assertEqual(normalized_homework_status(assignment, set(), today_iso="2026-05-12"), "expired")

    def test_tenant_isolation_data_level(self):
        row_a = clinical_meta("mood_1", "tenant_a", "client_a", "active", CLIENT_STATUSES, "active")
        row_b = clinical_meta("mood_2", "tenant_b", "client_b", "active", CLIENT_STATUSES, "active")
        self.assertNotEqual(row_a.tenant_id, row_b.tenant_id)

    def test_analytics_queryability(self):
        wellness = {
            "mood_entries": [{"data": "2026-05-10", "ansia": 5, "stress": 4, "umore_intensita": 3}],
            "homework_assignments": [{"id": "hw_1", "status": "assigned", "due_date": "2026-05-12", "assigned_at": "2026-05-10T09:00:00"}],
            "homework_submissions": [{"assignment_id": "hw_1"}],
        }
        rows = extract_structured_analytics_rows("client_a", "tenant_a", wellness)
        self.assertEqual(rows["mood_rows"][0]["tenant_id"], "tenant_a")
        self.assertEqual(rows["homework_rows"][0]["status"], "submitted")

    def test_repository_consistency(self):
        self.assertEqual(CHAT_STATUSES, {"active", "archived"})
        self.assertIn("generated", REPORT_STATUSES)
        self.assertIn("assigned", HOMEWORK_STATUSES)

    def test_backward_compatibility(self):
        wellness = {"mood_entries": [], "homework_assignments": [], "homework_submissions": []}
        rows = extract_structured_analytics_rows("client_a", "tenant_a", wellness)
        self.assertEqual(rows["mood_rows"], [])
        self.assertEqual(rows["homework_rows"], [])


if __name__ == "__main__":
    unittest.main()
