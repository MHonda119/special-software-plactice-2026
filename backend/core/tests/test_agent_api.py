from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient
from core.models import LLM, Agent, ChatSession
from core.llm_clients import ChatResult


class AgentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.llm = LLM.objects.create(
            name="Local",
            provider="OLLAMA",
            model="llama3",
            extra={"temperature": 0.2, "max_tokens": 100},
        )
        self.agent = Agent.objects.create(
            name="Basic Chat Bot",
            usecase_type="BASIC_CHAT",
            llm=self.llm,
            system_prompt="You are helpful.",
            config={"temperature": 0.5, "top_p": 0.9},
        )

    def fake_client_factory(self, *args, **kwargs):  # noqa: D401 - simple stub
        class Dummy:
            def __init__(self_inner):
                self_inner.captured_options = None

            def chat(self_inner, messages, options=None):  # noqa: D401
                self_inner.captured_options = options
                return ChatResult(content="OK", usage={"eval_count": 1})

        return Dummy()

    def test_agent_create_success(self):
        payload = {
            "name": "Another",
            "usecase_type": "BASIC_CHAT",
            "llm": self.llm.id,
            "system_prompt": "Sys",
            "config": {"temperature": 0.3},
        }
        r = self.client.post("/api/agents/", payload, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["name"], "Another")

    def test_agent_create_unsupported_usecase(self):
        # RAG_CHAT は現在サポートされるため成功を期待
        payload = {
            "name": "Rag Agent",
            "usecase_type": "RAG_CHAT",
            "llm": self.llm.id,
            "config": {"top_k": 3, "datasource_ids": [999]},  # 仮 ID
        }
        r = self.client.post("/api/agents/", payload, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["usecase_type"], "RAG_CHAT")

    def test_execute_creates_new_session_and_system_once(self):
        with patch("core.views.build_llm_client", self.fake_client_factory):
            r = self.client.post(
                f"/api/agents/{self.agent.id}/execute/",
                {"input": "Hello"},
                format="json",
            )
        self.assertEqual(r.status_code, 200, r.content)
        session_uuid = r.data["session_uuid"]
        session = ChatSession.objects.get(uuid=session_uuid)
        system_count = session.messages.filter(role="system").count()
        self.assertEqual(system_count, 1)

        # second execute using same session -> no duplicate system
        with patch("core.views.build_llm_client", self.fake_client_factory):
            r2 = self.client.post(
                f"/api/agents/{self.agent.id}/execute/",
                {"input": "Next", "session_uuid": session_uuid},
                format="json",
            )
        self.assertEqual(r2.status_code, 200)
        system_count_after = session.messages.filter(role="system").count()
        self.assertEqual(system_count_after, 1)

    def test_execute_existing_session(self):
        # prepare a session manually
        session = ChatSession.objects.create(llm=self.llm, agent=self.agent)
        with patch("core.views.build_llm_client", self.fake_client_factory):
            r = self.client.post(
                f"/api/agents/{self.agent.id}/execute/",
                {"input": "Reuse", "session_uuid": str(session.uuid)},
                format="json",
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["session_uuid"], str(session.uuid))
        # messages should include user + assistant (+ optional system)
        roles = list(session.messages.values_list("role", flat=True))
        # system may not exist because we created empty session manually
        self.assertIn("assistant", roles)
        self.assertIn("user", roles)

    def test_execute_empty_input(self):
        r = self.client.post(
            f"/api/agents/{self.agent.id}/execute/",
            {"input": ""},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_options_merge_precedence(self):
        captured: dict = {}

        def factory(*args, **kwargs):  # closure capturing created instance
            inst = self.fake_client_factory()
            captured["inst"] = inst
            return inst

        with patch("core.views.build_llm_client", factory):
            r = self.client.post(
                f"/api/agents/{self.agent.id}/execute/",
                {
                    "input": "Opts",
                    "options": {"temperature": 0.7, "max_tokens": 50},
                },
                format="json",
            )
        self.assertEqual(r.status_code, 200)
        merged = captured["inst"].captured_options
        # Precedence: request > agent.config > llm.extra
        self.assertEqual(merged["temperature"], 0.7)  # request overrides both
        self.assertEqual(merged["top_p"], 0.9)  # from agent.config
        # request overrides llm.extra 100
        self.assertEqual(merged["max_tokens"], 50)

    def test_session_uuid_must_belong_to_agent(self):
        other_agent = Agent.objects.create(
            name="Other",
            usecase_type="BASIC_CHAT",
            llm=self.llm,
        )
        # create session for other agent
        other_session = ChatSession.objects.create(
            llm=self.llm,
            agent=other_agent,
        )
        r = self.client.post(
            f"/api/agents/{self.agent.id}/execute/",
            {"input": "Hi", "session_uuid": str(other_session.uuid)},
            format="json",
        )
        self.assertEqual(r.status_code, 404)
        self.assertIn(b"Session not found", r.content)

    def test_system_prompt_not_inserted_if_missing(self):
        # Agent without system_prompt
        agent2 = Agent.objects.create(
            name="NoSys",
            usecase_type="BASIC_CHAT",
            llm=self.llm,
        )
        with patch("core.views.build_llm_client", self.fake_client_factory):
            r = self.client.post(
                f"/api/agents/{agent2.id}/execute/",
                {"input": "Ping"},
                format="json",
            )
        self.assertEqual(r.status_code, 200)
        session_uuid = r.data["session_uuid"]
        session = ChatSession.objects.get(uuid=session_uuid)
        self.assertEqual(session.messages.filter(role="system").count(), 0)
        self.assertEqual(session.messages.filter(role="assistant").count(), 1)
        self.assertEqual(session.messages.filter(role="user").count(), 1)
