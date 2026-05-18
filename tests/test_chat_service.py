import ast
import unittest
from pathlib import Path

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from services import chat_service
from services.chat_service import ChatContext, ChatResponse
from services.llm_prompt_service import build_llm_system_prompt


class ChatServiceTest(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "nome": "Giulia Rossi",
            "email": "giulia.rossi@example.com",
            "umore": "Ansioso",
            "stress": 8,
            "obiettivi": "Gestire meglio l'ansia al lavoro",
            "future_field": "Non deve entrare nel prompt",
        }
        self.wellness = {
            "mood_entries": [
                {
                    "data": "2026-05-16",
                    "umore": "Sereno",
                    "umore_intensita": 4,
                    "ansia": 3,
                    "stress": 4,
                    "trigger": "Passeggiata",
                },
                {
                    "data": "2026-05-17",
                    "umore": "Irritabile",
                    "umore_intensita": 7,
                    "ansia": 6,
                    "stress": 8,
                    "trigger": "Ho litigato con Marco",
                },
                {
                    "data": "2026-05-18",
                    "umore": "Sovraccarico",
                    "umore_intensita": 8,
                    "ansia": 7,
                    "stress": 9,
                    "trigger": "Scadenza urgente con il capo",
                },
            ]
        }
        self.context = ChatContext(
            profile=self.profile,
            wellness=self.wellness,
            username="giulia",
            user_input="Mi sento in ansia oggi",
        )
        self.copyright_policy = "Policy copyright"

    def test_builder_prompt_uses_same_minimized_system_prompt(self):
        prompt = chat_service.build_chat_prompt(self.context, self.copyright_policy)
        messages = prompt.format_messages(input=self.context.user_input, history=[])

        self.assertEqual(messages[0].content, build_llm_system_prompt(self.profile, self.wellness, self.copyright_policy))
        self.assertEqual(messages[-1].content, self.context.user_input)

    def test_minimization_is_unchanged_in_chat_prompt(self):
        system_prompt = chat_service.build_system_prompt(self.context, self.copyright_policy)

        self.assertIn("umore: Ansioso", system_prompt)
        self.assertIn("stress: 8", system_prompt)
        self.assertIn("obiettivi: Gestire meglio l'ansia al lavoro", system_prompt)
        self.assertIn("area trigger relazioni", system_prompt)
        self.assertIn("area trigger stress lavorativo", system_prompt)
        self.assertNotIn("Giulia Rossi", system_prompt)
        self.assertNotIn("giulia.rossi@example.com", system_prompt)
        self.assertNotIn("future_field", system_prompt)
        self.assertNotIn("Non deve entrare nel prompt", system_prompt)

    def test_service_has_no_streamlit_dependency(self):
        source = Path("services/chat_service.py").read_text()
        tree = ast.parse(source)
        imported_roots = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.append(node.module.split(".")[0])

        self.assertNotIn("streamlit", imported_roots)
        self.assertNotIn("st.", source)
        self.assertNotIn("session_state", source)

    def test_response_uses_mock_provider(self):
        seen_prompts = []

        def fake_provider(prompt_value):
            seen_prompts.append(prompt_value)
            return AIMessage(content="Risposta mock")

        response = chat_service.get_response(
            self.context,
            api_key="not-used-with-mock",
            copyright_policy=self.copyright_policy,
            chat_model=RunnableLambda(fake_provider),
        )

        self.assertEqual(response, ChatResponse(content="Risposta mock"))
        self.assertEqual(len(seen_prompts), 1)
        formatted_messages = seen_prompts[0].to_messages()
        self.assertEqual(len(formatted_messages), 2)
        self.assertEqual(formatted_messages[0].type, "system")
        self.assertEqual(formatted_messages[1].type, "human")
        self.assertEqual(formatted_messages[1].content, self.context.user_input)

    def test_get_response_regression_returns_response_dto_content(self):
        response = chat_service.get_response(
            self.context,
            api_key="not-used-with-mock",
            copyright_policy=self.copyright_policy,
            chat_model=RunnableLambda(lambda _: AIMessage(content="Contenuto finale")),
        )

        self.assertIsInstance(response, ChatResponse)
        self.assertEqual(response.content, "Contenuto finale")

    def test_create_chat_model_keeps_current_groq_configuration(self):
        model = chat_service.create_chat_model("fake-key")

        self.assertEqual(model.model_name, chat_service.CHAT_MODEL_NAME)
        self.assertEqual(chat_service.CHAT_MODEL_NAME, "llama-3.1-8b-instant")
        self.assertEqual(model.temperature, chat_service.CHAT_TEMPERATURE)
        self.assertEqual(chat_service.CHAT_TEMPERATURE, 0.50)


if __name__ == "__main__":
    unittest.main()
