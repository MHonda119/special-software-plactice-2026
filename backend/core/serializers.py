from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from .models import LLM, ChatSession, Message, Agent, Datasource


class LLMSerializer(serializers.ModelSerializer):
    class Meta:
        model = LLM
        fields = [
            "id",
            "name",
            "provider",
            "base_url",
            "model",
            "extra",
            "is_active",
        ]


class LLMCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LLM
        fields = [
            "id",
            "name",
            "provider",
            "base_url",
            "model",
            "api_key",
            "extra",
            "is_active",
        ]

    def validate(self, attrs):
        provider = attrs.get("provider") or getattr(self.instance, "provider", None)
        api_key = attrs.get("api_key") or getattr(self.instance, "api_key", None)
        if provider in {"OPENAI", "GEMINI"} and not api_key:
            raise ValidationError(
                {"api_key": ("This field is required for the selected provider.")}
            )
        return attrs


class ChatSessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ["uuid", "llm", "title"]
        read_only_fields = ["uuid"]


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "created_at"]


class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = [
            "id",
            "name",
            "usecase_type",
            "llm",
            "system_prompt",
            "config",
            "tools",
            "is_active",
        ]


class AgentCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = [
            "id",
            "name",
            "usecase_type",
            "llm",
            "system_prompt",
            "config",
            "tools",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate_usecase_type(self, value):
        # RAG_CHAT を許可 (拡張)。将来 CUSTOM など細分化予定。
        if value not in {"BASIC_CHAT", "RAG_CHAT"}:
            raise ValidationError("Unsupported usecase_type")
        return value


class AgentExecuteSerializer(serializers.Serializer):
    input = serializers.CharField(required=True, allow_blank=False)
    session_uuid = serializers.UUIDField(required=False)
    options = serializers.DictField(required=False)
    retrieval_overrides = serializers.DictField(required=False)


class AgentExecuteResponseSerializer(serializers.Serializer):
    agent_id = serializers.IntegerField()
    session_uuid = serializers.CharField()
    result = serializers.DictField()
    usage = serializers.DictField()


class DatasourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Datasource
        fields = [
            "id",
            "name",
            "description",
            "llm",
            "is_active",
        ]


class DatasourceCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Datasource
        fields = [
            "id",
            "name",
            "description",
            "llm",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate_name(self, value):
        if not value.strip():
            raise ValidationError("name is required")
        return value


class DatasourceChunkCreateSerializer(serializers.Serializer):
    title = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=200,
    )
    chunk_text = serializers.CharField(
        required=True, allow_blank=False, max_length=10000
    )

    def validate(self, attrs):
        title = attrs.get("title", "").strip()
        chunk_text = attrs.get("chunk_text", "").strip()
        if not title or not chunk_text:
            raise ValidationError({"detail": "title and chunk_text are required"})
        return attrs
