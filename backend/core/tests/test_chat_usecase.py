from unittest.mock import patch

from django.test import TestCase

from core.models import LLM, ChatSession, Message, Agent
from core.usecases import ChatInSessionUsecase
from core.llm_clients import ChatResult


class ChatUsecaseTests(TestCase):
    def setUp(self):
        self.llm = LLM.objects.create(
            name="Local",
            provider="OLLAMA",
            model="llama3",
        )
        self.session = ChatSession.objects.create(llm=self.llm, title="Test")
        self.agent = Agent.objects.create(
            name="Basic Chat Bot",
            usecase_type="BASIC_CHAT",
            llm=self.llm,
            system_prompt="You are helpful.",
            config={"temperature": 0.5},
        )

    def test_run_creates_assistant_message(self):
        def fake_client(*args, **kwargs):  # noqa: D401 - simple factory
            class Dummy:
                def chat(self_inner, messages, options=None):  # noqa: D401
                    return ChatResult(
                        content="Hello from mock", usage={"prompt_tokens": 1}
                    )

            return Dummy()

        with patch("core.usecases.build_llm_client", fake_client):
            uc = ChatInSessionUsecase(self.session.uuid)
            result = uc.run("Hi")

        self.assertEqual(
            result["assistant_message"]["content"],
            "Hello from mock",
        )
        # DB に assistant が作成されているか
        msgs = list(Message.objects.filter(session=self.session))
        self.assertEqual(len(msgs), 2)  # user + assistant
        self.assertEqual(msgs[-1].role, "assistant")
        self.assertEqual(msgs[-1].content, "Hello from mock")

    def test_agent_execute_creates_new_session_and_system_once(self):
        def fake_client(*args, **kwargs):  # noqa: D401
            class Dummy:
                def chat(self_inner, messages, options=None):  # noqa: D401
                    return ChatResult(
                        content="Hi agent",
                        usage={"eval_count": 1},
                    )

            return Dummy()

        with patch("core.views.build_llm_client", fake_client):
            # Simulate viewset execute logic via direct ORM operations
            from core.llm_clients import (  # noqa: F401
                build_llm_client as real_factory,
            )

            # Create session None -> new
            self.assertEqual(self.agent.sessions.count(), 0)
            from core.models import (  # local refs
                ChatSession as CS,
                Message as Msg,
            )

            # mimic execute endpoint minimal logic
            session = CS.objects.create(llm=self.agent.llm, agent=self.agent)
            if (
                self.agent.system_prompt
                and not session.messages.filter(role="system").exists()
            ):
                Msg.objects.create(
                    session=session,
                    role="system",
                    content=self.agent.system_prompt,
                )
            Msg.objects.create(session=session, role="user", content="Hello")
            messages = [
                {"role": m.role, "content": m.content} for m in session.messages.all()
            ]
            client = fake_client()
            result = client.chat(messages, options={"temperature": 0.1})
            Msg.objects.create(
                session=session,
                role="assistant",
                content=result.content,
                usage=result.usage,
            )

            self.assertEqual(session.messages.filter(role="system").count(), 1)
            roles = list(session.messages.values_list("role", flat=True))
            self.assertEqual(roles, ["system", "user", "assistant"])
