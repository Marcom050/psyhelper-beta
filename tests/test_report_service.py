import inspect
import unittest

from services import report_service
from services.report_service import (
    ClinicalReport,
    ReportSection,
    WeeklyRecap,
    build_timeline_events,
    clinical_snapshot,
    mood_entries_dataframe,
    weekly_recap,
)


class ReportServiceTest(unittest.TestCase):
    def setUp(self):
        self.now = "2026-05-18"
        self.complete_wellness = {
            "mood_entries": [
                {
                    "creata_il": "2026-05-10T09:00:00",
                    "data": "2026-05-10",
                    "umore": "Ansioso",
                    "umore_intensita": 7,
                    "ansia": 6,
                    "stress": 5,
                    "trigger": "lavoro",
                    "sensazioni": ["Tensione muscolare", "Nodo allo stomaco"],
                    "bisogno": "riposo",
                    "pensiero_automatico": "Andrà malissimo al lavoro",
                    "comportamento": "evito la riunione",
                    "risposta_alternativa": "Posso preparare una scaletta",
                    "nota_professionista": "Valutare evitamento.",
                },
                {
                    "creata_il": "2026-05-12T10:00:00",
                    "data": "2026-05-12",
                    "umore": "Ansioso",
                    "umore_intensita": 8,
                    "ansia": 8,
                    "stress": 7,
                    "trigger": "lavoro",
                    "sensazioni": ["Tensione muscolare"],
                    "bisogno": "chiarezza",
                    "pensiero_automatico": "Sarà un disastro con il capo",
                    "comportamento": "mi isolo",
                    "risposta_alternativa": "Posso chiedere feedback",
                    "nota_professionista": "Portare esempio del capo.",
                },
            ],
            "homework_assignments": [
                {"id": "hw-1", "template": "ABC", "assigned_at": "2026-05-11T12:00:00", "due_date": "2026-05-15", "instructions": "Compila ABC"},
                {"id": "hw-2", "template": "Respirazione", "assigned_at": "2026-05-13T12:00:00", "due_date": "2026-05-14", "instructions": "Esercizio"},
            ],
            "homework_submissions": [
                {"assignment_id": "hw-1", "template": "ABC", "submitted_at": "2026-05-12T18:00:00", "summary": "ABC completato"},
            ],
            "timeline_events": [
                {"data": "2026-05-16T10:00:00", "tipo": "Evento clinico", "titolo": "Seduta", "dettaglio": "Focus evitamento"},
            ],
        }

    def test_report_with_empty_wellness_returns_pure_dto(self):
        report = clinical_snapshot({}, now=self.now)

        self.assertIsInstance(report, ClinicalReport)
        self.assertEqual(report.entries_count, 0)
        self.assertEqual(report.avg_anxiety, 0)
        self.assertEqual(report.avg_stress, 0)
        self.assertEqual(report.last_activity, "—")
        self.assertEqual(report.export_text, "")
        self.assertTrue(report.scope_df.empty)
        self.assertIn("Nessuna scheda compilata: aderenza non valutabile.", report.alerts)

    def test_report_with_complete_data_builds_stats_sections_and_preserves_wellness_shape(self):
        report = clinical_snapshot(self.complete_wellness, [{"content": "tema sociale e lavoro"}], now=self.now)

        self.assertIsInstance(report, ClinicalReport)
        self.assertEqual(report.entries_count, 2)
        self.assertEqual(report.avg_anxiety, 7)
        self.assertEqual(report.avg_stress, 6)
        self.assertEqual(report.homework_total, 2)
        self.assertEqual(report.homework_completed, 1)
        self.assertEqual(report.homework_compliance, 50)
        self.assertEqual(report.last_activity, "2026-05-12")
        self.assertIn("Trigger ricorrente: lavoro (2 rilevazioni).", report.insights)
        self.assertIn("Forte intensità emotiva recente: potenziale area da attenzionare.", report.alerts)
        self.assertIn("1 homework assegnati risultano oltre scadenza.", report.alerts)
        self.assertEqual([section.title for section in report.sections], [
            "Stati d'animo più frequenti",
            "Trigger ricorrenti",
            "Sensazioni corporee ricorrenti",
            "Ultime note per il professionista",
        ])
        self.assertTrue(all(isinstance(section, ReportSection) for section in report.sections))
        self.assertIn("homework_assignments", self.complete_wellness)
        self.assertIn("homework_submissions", self.complete_wellness)
        self.assertIn("timeline_events", self.complete_wellness)

    def test_weekly_recap_returns_dto_with_existing_text_content(self):
        report = clinical_snapshot(self.complete_wellness, now=self.now)
        recap = weekly_recap(report)

        self.assertIsInstance(recap, WeeklyRecap)
        self.assertEqual(recap[0], "Schede ultime 2 settimane: 2")
        self.assertIn("Ansia media: 7.0/10", recap.items)
        self.assertIn("Stress medio: 6.0/10", recap.items)
        self.assertIn("Homework completati: 1 su 2 (50%)", recap.items)
        self.assertEqual(recap.to_text(bullet_prefix="- ").splitlines()[0], "- Schede ultime 2 settimane: 2")

    def test_timeline_events_include_diary_homework_submissions_and_manual_events_sorted(self):
        events = build_timeline_events(self.complete_wellness)

        self.assertEqual(events[0]["tipo"], "Evento clinico")
        self.assertEqual(events[1]["tipo"], "Homework assegnato")
        self.assertEqual(events[2]["tipo"], "Homework completato")
        self.assertTrue(any(event["tipo"] == "Diario" and "ansia 8/10" in event["titolo"] for event in events))

    def test_export_regression_matches_existing_txt_format(self):
        report = clinical_snapshot(self.complete_wellness, now=self.now)

        expected = "\n".join([
            "RESOCONTO PSYHELPER",
            "Periodo: 2026-05-10 - 2026-05-12",
            "Schede compilate: 2",
            "Ansia media: 7.0/10",
            "Stress medio: 6.0/10",
            "Intensità emotiva media: 7.5/10",
            "",
            "Stati d'animo più frequenti:",
            "- Ansioso: 2",
            "",
            "Trigger ricorrenti:",
            "- lavoro: 2",
            "",
            "Sensazioni corporee ricorrenti:",
            "- Tensione muscolare: 2",
            "- Nodo allo stomaco: 1",
            "",
            "Ultime note per il professionista:",
            "- Valutare evitamento.",
            "- Portare esempio del capo.",
        ])
        self.assertEqual(report.export_text, expected)

    def test_service_has_no_streamlit_import_or_session_adapter_dependency(self):
        source = inspect.getsource(report_service)

        self.assertNotIn("import streamlit", source)
        self.assertNotIn("from streamlit", source)
        self.assertNotIn("SessionAdapter", source)

    def test_mood_entries_dataframe_handles_empty_wellness(self):
        self.assertTrue(mood_entries_dataframe({}).empty)


if __name__ == "__main__":
    unittest.main()
