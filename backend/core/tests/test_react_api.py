from unittest.mock import patch
from uuid import uuid4

import httpx
from django.contrib.auth import get_user_model
from django.test import TestCase
from openai import APIConnectionError, APITimeoutError
from rest_framework.test import APIClient

from core.models import Agent, ChatSession, LLM, Message
from core.react_runner import ReActError, ReActLimitError, ReActResult


class ReActApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(
            get_user_model().objects.create_user("student")
        )
        self.llm = LLM.objects.create(
            name="GPT-6 luna",
            provider="OPENAI",
            model="gpt-6-luna",
            api_key="unused",
            extra={"max_steps": 2},
        )
        self.agent = Agent.objects.create(
            name="ReAct",
            usecase_type="REACT_CHAT",
            llm=self.llm,
            config={"max_steps": 4},
            system_prompt="講義用の商品について回答する。",
        )
        self.url = f"/api/agents/{self.agent.id}/execute/"

    def test_create_accepts_react_chat_and_rejects_custom(self):
        body = {
            "name": "New",
            "usecase_type": "REACT_CHAT",
            "llm": self.llm.id,
        }

        result = self.client.post(
            "/api/agents/",
            body,
            format="json",
        )

        self.assertEqual(result.status_code, 201)
        self.assertEqual(
            result.data["usecase_type"],
            "REACT_CHAT",
        )

        body["usecase_type"] = "CUSTOM"

        result = self.client.post(
            "/api/agents/",
            body,
            format="json",
        )

        self.assertEqual(result.status_code, 400)

    def test_success_uses_usecase_and_returns_message(self):
        with (
            patch("core.views.open_react_client"),
            patch("core.views.ReActRunner") as runner_class,
        ):
            runner_class.return_value.run.return_value = ReActResult(
                content="250円です。",
                usage={"total_tokens": 12},
            )

            result = self.client.post(
                self.url,
                {"input": "質問"},
                format="json",
            )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            result.data["agent_id"],
            self.agent.id,
        )
        self.assertEqual(
            result.data["result"]["message"]["content"],
            "250円です。",
        )

        session = ChatSession.objects.get(
            uuid=result.data["session_uuid"]
        )

        self.assertEqual(
            session.agent_id,
            self.agent.id,
        )
        self.assertEqual(
            session.messages.count(),
            2,
        )
        self.assertEqual(
            runner_class.call_args.kwargs["model"],
            "gpt-6-luna",
        )
        self.assertEqual(
            runner_class.call_args.kwargs["system_prompt"],
            self.agent.system_prompt,
        )

    def test_invalid_input_returns_400_before_client_creation(self):
        for body in [
            {},
            {"input": "  "},
            {"input": "x" * 2001},
            {
                "input": "質問",
                "session_uuid": "invalid",
            },
            {
                "input": "質問",
                "options": {"max_steps": 0},
            },
            {
                "input": "質問",
                "options": {"max_steps": 9},
            },
            {
                "input": "質問",
                "options": {"max_steps": "invalid"},
            },
        ]:
            with self.subTest(body=body):
                with patch(
                    "core.views.open_react_client"
                ) as factory:
                    result = self.client.post(
                        self.url,
                        body,
                        format="json",
                    )

                self.assertEqual(
                    result.status_code,
                    400,
                )
                factory.assert_not_called()

        self.assertEqual(
            self.agent.sessions.count(),
            0,
        )

    def test_missing_inactive_and_foreign_sessions_return_404(self):
        inactive = ChatSession.objects.create(
            agent=self.agent,
            llm=self.llm,
            is_active=False,
        )

        other_agent = Agent.objects.create(
            name="Other",
            usecase_type="REACT_CHAT",
            llm=self.llm,
        )

        foreign = ChatSession.objects.create(
            agent=other_agent,
            llm=self.llm,
        )

        standalone = ChatSession.objects.create(
            llm=self.llm
        )

        for session_uuid in [
            uuid4(),
            inactive.uuid,
            foreign.uuid,
            standalone.uuid,
        ]:
            with self.subTest(
                session_uuid=session_uuid
            ):
                with (
                    patch("core.views.open_react_client"),
                    patch(
                        "core.views.ReActRunner"
                    ) as runner_class,
                ):
                    result = self.client.post(
                        self.url,
                        {
                            "input": "質問",
                            "session_uuid": str(
                                session_uuid
                            ),
                        },
                        format="json",
                    )

                self.assertEqual(
                    result.status_code,
                    404,
                )
                runner_class.return_value.run.assert_not_called()

        self.assertEqual(
            Message.objects.count(),
            0,
        )

    def test_missing_and_inactive_agents_return_404(self):
        self.agent.is_active = False
        self.agent.save(
            update_fields=["is_active"]
        )

        for agent_id in [
            self.agent.id,
            self.agent.id + 1000,
        ]:
            with self.subTest(agent_id=agent_id):
                with patch(
                    "core.views.open_react_client"
                ) as factory:
                    result = self.client.post(
                        f"/api/agents/{agent_id}/execute/",
                        {"input": "質問"},
                        format="json",
                    )

                self.assertEqual(
                    result.status_code,
                    404,
                )
                factory.assert_not_called()

    def test_invalid_llm_returns_422(self):
        for provider, active, key in [
            ("OLLAMA", True, "unused"),
            ("OPENAI", False, "unused"),
            ("OPENAI", True, ""),
        ]:
            with self.subTest(
                provider=provider,
                active=active,
                key_present=bool(key),
            ):
                self.llm.provider = provider
                self.llm.is_active = active
                self.llm.api_key = key
                self.llm.save(
                    update_fields=[
                        "provider",
                        "is_active",
                        "api_key",
                    ]
                )

                result = self.client.post(
                    self.url,
                    {"input": "質問"},
                    format="json",
                )

                self.assertEqual(
                    result.status_code,
                    422,
                )
                self.assertEqual(
                    self.agent.sessions.count(),
                    0,
                )

    def test_options_follow_existing_merge_order(self):
        for options, expected_steps in [
            ({}, 4),
            ({"max_steps": 6}, 6),
        ]:
            with self.subTest(options=options):
                with (
                    patch("core.views.open_react_client"),
                    patch(
                        "core.views.ReActRunner"
                    ) as runner_class,
                ):
                    runner_class.return_value.run.return_value = (
                        ReActResult(
                            "回答",
                            {},
                        )
                    )

                    result = self.client.post(
                        self.url,
                        {
                            "input": "質問",
                            "options": options,
                        },
                        format="json",
                    )

                self.assertEqual(
                    result.status_code,
                    200,
                )
                self.assertEqual(
                    runner_class.call_args.kwargs[
                        "max_steps"
                    ],
                    expected_steps,
                )

    def test_invalid_defaults_return_422(self):
        for config in [
            [],
            {"max_steps": 0},
        ]:
            with self.subTest(config=config):
                self.agent.config = config
                self.agent.save(
                    update_fields=["config"]
                )

                with patch(
                    "core.views.open_react_client"
                ) as factory:
                    result = self.client.post(
                        self.url,
                        {"input": "質問"},
                        format="json",
                    )

                self.assertEqual(
                    result.status_code,
                    422,
                )
                factory.assert_not_called()

    def test_changed_agent_llm_does_not_reuse_old_llm_session(self):
        other_llm = LLM.objects.create(
            name="Old",
            provider="OPENAI",
            model="old-model",
        )

        session = ChatSession.objects.create(
            agent=self.agent,
            llm=other_llm,
        )

        with patch(
            "core.views.open_react_client"
        ):
            result = self.client.post(
                self.url,
                {
                    "input": "質問",
                    "session_uuid": str(
                        session.uuid
                    ),
                },
                format="json",
            )

        self.assertEqual(
            result.status_code,
            422,
        )
        self.assertEqual(
            session.messages.count(),
            0,
        )

    def test_upstream_errors_are_mapped_without_saving(self):
        request = httpx.Request(
            "POST",
            "https://example.invalid/v1/responses",
        )

        for error, expected_status in [
            (
                ReActLimitError("上限"),
                502,
            ),
            (
                ReActError("空回答"),
                502,
            ),
            (
                APIConnectionError(
                    request=request
                ),
                502,
            ),
            (
                APITimeoutError(
                    request=request
                ),
                504,
            ),
        ]:
            with self.subTest(
                error=type(error).__name__
            ):
                with (
                    patch("core.views.open_react_client"),
                    patch(
                        "core.views.ReActRunner"
                    ) as runner_class,
                ):
                    runner_class.return_value.run.side_effect = (
                        error
                    )

                    result = self.client.post(
                        self.url,
                        {"input": "質問"},
                        format="json",
                    )

                self.assertEqual(
                    result.status_code,
                    expected_status,
                )
                self.assertEqual(
                    self.agent.sessions.count(),
                    0,
                )
                self.assertEqual(
                    Message.objects.count(),
                    0,
                )
