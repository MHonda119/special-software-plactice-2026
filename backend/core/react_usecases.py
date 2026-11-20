from django.db import transaction

from .models import ChatSession, Message
from .react_runner import ReActConfigurationError


class ReActAgentUsecase:
    def __init__(self, agent, runner):
        if not agent.is_active or agent.usecase_type != "REACT_CHAT":
            raise ReActConfigurationError(
                "有効な ReAct Agent を指定してください。"
            )

        self.agent = agent
        self.runner = runner

    def run(self, user_text, session_uuid=None):
        if not isinstance(user_text, str) or not user_text.strip():
            raise ValueError("質問を入力してください。")

        user_text = user_text.strip()
        session = None
        messages = []

        if session_uuid is not None:
            session = ChatSession.objects.get(
                uuid=session_uuid,
                is_active=True,
                agent=self.agent,
            )

            if session.llm_id != self.agent.llm_id:
                raise ReActConfigurationError(
                    "会話と Agent の LLM 設定が異なります。"
                )

            messages = [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in session.messages.filter(
                    role__in=["user", "assistant"],
                ).order_by("created_at", "id")
            ]

        messages.append(
            {
                "role": "user",
                "content": user_text,
            }
        )

        result = self.runner.run(messages)

        with transaction.atomic():
            if session is None:
                session = ChatSession.objects.create(
                    agent=self.agent,
                    llm=self.agent.llm,
                )

            Message.objects.create(
                session=session,
                role="user",
                content=user_text,
            )

            assistant = Message.objects.create(
                session=session,
                role="assistant",
                content=result.content,
                usage=result.usage,
            )

        return {
            "agent_id": self.agent.id,
            "session_uuid": str(session.uuid),
            "result": {
                "message": {
                    "id": assistant.id,
                    "role": assistant.role,
                    "content": assistant.content,
                },
            },
            "usage": result.usage,
        }
