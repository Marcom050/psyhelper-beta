import importlib
import inspect
import unittest
from datetime import date, datetime

from services import homework_service as homework


class HomeworkServiceTest(unittest.TestCase):
    def test_cbt_homework_templates_are_ordered_and_have_italian_visible_copy(self):
        self.assertEqual(
            list(homework.CBT_HOMEWORK_TEMPLATES.keys()),
            [
                "Respiro 3 minuti",
                "Pensiero più realistico",
                "Piccolo passo evitato",
                "Tempo per le preoccupazioni",
                "Azione di cura",
                "Nota per la seduta",
            ],
        )
        respiro = homework.CBT_HOMEWORK_TEMPLATES["Respiro 3 minuti"]
        self.assertEqual(respiro["titolo"], "Respiro guidato di 3 minuti")
        self.assertIn("osservare", respiro["obiettivo"].lower())
        self.assertTrue(homework.clean_text(respiro["campi"][0]))
        self.assertEqual(homework.homework_template_label("Nota per la seduta"), "Nota da portare in seduta")

        self.assertEqual(
            homework.homework_main_prompt("Nota per la seduta"),
            "Che cosa vorresti portare in seduta?",
        )

    def test_create_assignment_preserves_existing_wellness_format(self):
        created = homework.create_assignment(
            "Azione di cura",
            date(2026, 5, 20),
            "therapist_a",
            prompt="  Fai una passeggiata e annota l'umore.  ",
            now=datetime(2026, 5, 18, 12, 30, 45),
        )

        self.assertEqual(
            created,
            {
                "id": "hw_20260518123045",
                "template": "Azione di cura",
                "objective": "Questa scheda ti aiuta a scegliere una piccola azione concreta di cura verso di te e a osservare l'effetto che ha.",
                "instructions": "Quando pensi di farla? Com'era il tuo stato prima e com'è stato dopo averla fatta?",
                "questions": ["Fai una passeggiata e annota l'umore."],
                "due_date": "2026-05-20",
                "assigned_at": "2026-05-18T12:30:45",
                "assigned_by": "therapist_a",
            },
        )
        self.assertTrue(homework.validate_assignment(created))

    def test_create_submission_preserves_summary_and_answer_format(self):
        submission = homework.create_submission(
            "hw_1",
            "Respiro 3 minuti",
            "Ansia prima/dopo?",
            "Prima 7, dopo 4",
            now=datetime(2026, 5, 18, 13, 0, 1),
        )

        self.assertEqual(
            submission,
            {
                "assignment_id": "hw_1",
                "template": "Respiro 3 minuti",
                "submitted_at": "2026-05-18T13:00:01",
                "answers": {"Ansia prima/dopo?": "Prima 7, dopo 4"},
                "summary": "Prima 7, dopo 4",
            },
        )
        self.assertTrue(homework.validate_submission(submission))

    def test_validations_reject_invalid_shapes(self):
        self.assertFalse(homework.validate_assignment({"id": "hw_1"}))
        self.assertFalse(
            homework.validate_assignment(
                {
                    "id": "hw_1",
                    "template": "Nota",
                    "objective": "",
                    "instructions": "",
                    "questions": "not-a-list",
                    "due_date": "2026-05-20",
                    "assigned_at": "2026-05-18T12:00:00",
                    "assigned_by": "therapist",
                }
            )
        )
        self.assertFalse(homework.validate_submission({"assignment_id": "hw_1"}))
        self.assertFalse(
            homework.validate_submission(
                {
                    "assignment_id": "hw_1",
                    "template": "Nota",
                    "submitted_at": "2026-05-18T12:00:00",
                    "answers": ["not-a-dict"],
                    "summary": "",
                }
            )
        )

    def test_status_pending_completed_and_overdue(self):
        assignments = [
            {"id": "hw_done", "template": "Nota per la seduta", "due_date": "2026-05-20", "questions": []},
            {"id": "hw_pending", "template": "Nota per la seduta", "due_date": "2026-05-20", "questions": []},
            {"id": "hw_late", "template": "Nota per la seduta", "due_date": "2026-05-17", "questions": []},
        ]
        submissions = [{"assignment_id": "hw_done", "template": "Nota per la seduta", "answers": {}, "summary": "", "submitted_at": "2026-05-18T10:00:00"}]
        statuses = homework.homework_statuses(assignments, submissions, today=date(2026, 5, 18))

        self.assertEqual([item.status for item in statuses], ["Completato", "Da completare", "Scaduto"])
        self.assertEqual(homework.get_open_assignments(assignments, submissions), assignments[1:])

    def test_existing_wellness_compatibility_and_ordering(self):
        wellness = {
            "homework_assignments": [{"id": "hw_1", "template": "Nota per la seduta", "due_date": "2026-05-20", "questions": ["Q"]}],
            "homework_submissions": [
                {"assignment_id": "hw_1", "template": "Nota per la seduta", "answers": {"Q": "Prima"}, "summary": "", "submitted_at": "2026-05-18T09:00:00"},
                {"assignment_id": None, "template": "Azione di cura", "answers": {"Q": "Dopo"}, "summary": "", "submitted_at": "2026-05-18T10:00:00"},
            ],
        }

        self.assertIs(homework.get_assigned_homework(wellness), wellness["homework_assignments"])
        self.assertIs(homework.get_submitted_homework(wellness), wellness["homework_submissions"])
        self.assertEqual(
            homework.submitted_homework_rows(wellness["homework_submissions"], display_defaults=False),
            [
                {"data": "2026-05-18T10:00:00", "homework": "Azione di cura", "sintesi": "Dopo"},
                {"data": "2026-05-18T09:00:00", "homework": "Nota per la seduta", "sintesi": "Prima"},
            ],
        )

    def test_service_has_no_streamlit_dependency(self):
        source = inspect.getsource(importlib.import_module("services.homework_service"))
        self.assertNotIn("import streamlit", source)
        self.assertNotIn("st.session_state", source)
        self.assertNotIn("st.", source)

    def test_dashboard_regression_helpers_keep_client_and_therapist_rows(self):
        assignments = [{"id": "hw_1", "template": "Nota per la seduta", "due_date": "2026-05-20", "questions": ["Nota?"]}]
        submissions = [{"assignment_id": "hw_1", "template": "Nota per la seduta", "answers": {"Nota?": "Parlarne in seduta"}, "summary": "", "submitted_at": "2026-05-18T10:00:00"}]
        completed_ids = homework.completed_assignment_ids(submissions)

        self.assertEqual(
            homework.homework_assignment_rows(assignments, completed_ids),
            [{"homework": "Nota per la seduta", "scadenza": "2026-05-20", "stato": "Completato", "consegna": "Nota?"}],
        )
        self.assertEqual(
            homework.submitted_homework_rows(submissions),
            [{"data": "2026-05-18T10:00:00", "homework": "Nota per la seduta", "sintesi": "Parlarne in seduta"}],
        )

    def test_homework_templates_avoid_diagnostic_or_automatic_clinical_language(self):
        forbidden_terms = ["diagnosi", "disturbo", "trattamento automatico", "valutazione clinica automatica"]
        for template in homework.CBT_HOMEWORK_TEMPLATES.values():
            visible_text = " ".join([
                str(template.get("titolo", "")),
                str(template.get("obiettivo", "")),
                " ".join(template.get("campi", [])),
                str(template.get("suggerimento", "")),
            ]).lower()
            for term in forbidden_terms:
                self.assertNotIn(term, visible_text)

    def test_format_homework_status_label_mapping_keeps_internal_statuses_stable(self):
        self.assertEqual(homework.format_homework_status_label("assigned"), "Assegnato")
        self.assertEqual(homework.format_homework_status_label("in_progress"), "In compilazione")
        self.assertEqual(homework.format_homework_status_label("Completato"), "Completato")



if __name__ == "__main__":
    unittest.main()
