from unittest.mock import Mock, patch

from django.test import TestCase

from core.models import Agent, ChatSession, LLM, Message
from core.react_runner import ReActLimitError, ReActResult
from core.react_usecases import ReActAgentUsecase


class ReActUsecaseTests(TestCase):
    def setUp(self):
        self.llm = LLM.objects.create(
            name="GPT-6 luna", provider="OPENAI", model="gpt-6-luna",
        )
        self.agent = Agent.objects.create(
            name="ReAct", usecase_type="REACT_CHAT", llm=self.llm,
        )
        self.session = ChatSession.objects.create(llm=self.llm, agent=self.agent)
        self.runner = Mock()
        self.runner.run.return_value = ReActResult(
            content="お釣りは250円です。", usage={"total_tokens": 12},
        )

    def test_success_creates_session_user_and_assistant(self):
        result = ReActAgentUsecase(self.agent, self.runner).run("質問")
        session = ChatSession.objects.get(uuid=result["session_uuid"])

        self.assertEqual(result["agent_id"], self.agent.id)
        self.assertEqual(session.agent_id, self.agent.id)
        self.assertEqual(session.llm_id, self.llm.id)
        self.assertEqual(result["result"]["message"]["content"], "お釣りは250円です。")
        self.assertEqual(
            list(session.messages.values_list("role", flat=True)),
            ["user", "assistant"],
        )
        self.assertEqual(session.messages.last().usage, {"total_tokens": 12})

    def test_next_turn_receives_previous_messages(self):
        usecase = ReActAgentUsecase(self.agent, self.runner)
        first = usecase.run("最初の質問")
        second = usecase.run("ではペン2本なら？", session_uuid=first["session_uuid"])

        received = self.runner.run.call_args.args[0]
        self.assertEqual([item["role"] for item in received], [
            "user", "assistant", "user",
        ])
        self.assertEqual(received[0]["content"], "最初の質問")
        self.assertEqual(received[-1]["content"], "ではペン2本なら？")
        self.assertEqual(first["session_uuid"], second["session_uuid"])
        session = ChatSession.objects.get(uuid=first["session_uuid"])
        self.assertEqual(session.messages.count(), 4)
        self.assertEqual(session.messages.filter(role="system").count(), 0)

    def test_runner_failure_leaves_existing_history_unchanged(self):
        Message.objects.create(session=self.session, role="user", content="過去の質問")
        previous_ids = list(self.session.messages.values_list("id", flat=True))
        self.runner.run.side_effect = ReActLimitError("上限")

        with self.assertRaises(ReActLimitError):
            ReActAgentUsecase(self.agent, self.runner).run(
                "新しい質問", session_uuid=self.session.uuid,
            )

        self.assertEqual(
            list(self.session.messages.values_list("id", flat=True)), previous_ids,
        )

    def test_first_runner_failure_does_not_create_empty_session(self):
        previous_count = self.agent.sessions.count()
        self.runner.run.side_effect = ReActLimitError("上限")
        with self.assertRaises(ReActLimitError):
            ReActAgentUsecase(self.agent, self.runner).run("質問")
        self.assertEqual(self.agent.sessions.count(), previous_count)
        self.assertEqual(Message.objects.count(), 0)

    def test_assistant_save_failure_rolls_back_new_session_and_user(self):
        previous_count = self.agent.sessions.count()
        original_create = Message.objects.create

        def persist(**fields):
            if fields["role"] == "assistant":
                raise RuntimeError("保存失敗の再現")
            return original_create(**fields)

        with patch("core.react_usecases.Message.objects.create", side_effect=persist):
            with self.assertRaises(RuntimeError):
                ReActAgentUsecase(self.agent, self.runner).run("質問")

        self.assertEqual(self.agent.sessions.count(), previous_count)
        self.assertEqual(Message.objects.count(), 0)

    def test_assistant_save_failure_rolls_back_existing_session_user(self):
        original_create = Message.objects.create

        def persist(**fields):
            if fields["role"] == "assistant":
                raise RuntimeError("保存失敗の再現")
            return original_create(**fields)

        with patch("core.react_usecases.Message.objects.create", side_effect=persist):
            with self.assertRaises(RuntimeError):
                ReActAgentUsecase(self.agent, self.runner).run(
                    "質問", session_uuid=self.session.uuid,
                )
        self.assertEqual(self.session.messages.count(), 0)

    def test_foreign_session_is_not_passed_to_runner(self):
        other_agent = Agent.objects.create(
            name="Other", usecase_type="REACT_CHAT", llm=self.llm,
        )
        other_session = ChatSession.objects.create(llm=self.llm, agent=other_agent)
        with self.assertRaises(ChatSession.DoesNotExist):
            ReActAgentUsecase(self.agent, self.runner).run(
                "質問", session_uuid=other_session.uuid,
            )
        self.runner.run.assert_not_called()
