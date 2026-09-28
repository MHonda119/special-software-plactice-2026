from django.db import transaction
from .models import ChatSession, Message
from .llm_clients import build_llm_client


class ChatInSessionUsecase:
    def __init__(self, session_uuid):
        self.session = ChatSession.objects.select_related("llm").get(
            uuid=session_uuid, is_active=True
        )

    @transaction.atomic
    def run(self, user_text: str, options: dict | None = None) -> dict:
        Message.objects.create(
            session=self.session,
            role="user",
            content=user_text,
        )

        messages = [
            {"role": m.role, "content": m.content} for m in self.session.messages.all()
        ]

        client = build_llm_client(self.session.llm)
        result = client.chat(messages, options=options)

        assistant = Message.objects.create(
            session=self.session,
            role="assistant",
            content=result.content,
            usage=result.usage,
        )

        return {
            "session_uuid": str(self.session.uuid),
            "assistant_message": {
                "id": assistant.id,
                "role": "assistant",
                "content": assistant.content,
            },
            "usage": result.usage,
        }
