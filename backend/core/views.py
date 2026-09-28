from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework import viewsets, status
from .models import LLM, ChatSession, Agent, Message, Datasource
from .serializers import (
    LLMSerializer,
    LLMCreateUpdateSerializer,
    ChatSessionCreateSerializer,
    MessageSerializer,
    AgentSerializer,
    AgentCreateUpdateSerializer,
    AgentExecuteSerializer,
    DatasourceSerializer,
    DatasourceCreateUpdateSerializer,
    DatasourceChunkCreateSerializer,
)
from .usecases import ChatInSessionUsecase
from .llm_clients import build_llm_client
from django.middleware.csrf import get_token
from .datasource_store import (
    add_chunk,
    EmbeddingError,
    drop_collection,
    list_chunks,
    delete_chunk,
)
from .rag_runner import RagChatRunner, RagResult

import logging

logger = logging.getLogger(__name__)


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
def csrf_token(request):
    """Issue CSRF token and return value."""
    token = get_token(request)
    return Response({"csrftoken": token})


class LLMViewSet(viewsets.ModelViewSet):
    queryset = LLM.objects.all()

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return LLMCreateUpdateSerializer
        return LLMSerializer


class ChatSessionViewSet(viewsets.ModelViewSet):
    queryset = ChatSession.objects.filter(is_active=True)
    serializer_class = ChatSessionCreateSerializer

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=["get"], url_path="messages")
    def messages(self, request, pk=None):
        session = self.get_object()
        qs = session.messages.all()
        return Response(MessageSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="chat")
    def chat(self, request, pk=None):
        message = request.data.get("message", "").strip()
        if not message:
            return Response(
                {"detail": "message is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        options = request.data.get("options", None)
        uc = ChatInSessionUsecase(pk)
        result = uc.run(user_text=message, options=options)
        return Response(result, status=status.HTTP_200_OK)


class AgentViewSet(viewsets.ModelViewSet):
    queryset = Agent.objects.filter(is_active=True)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return AgentCreateUpdateSerializer
        return AgentSerializer

    @action(detail=True, methods=["post"], url_path="execute")
    def execute(self, request, pk=None):
        agent = self.get_object()
        if not agent.is_active:
            return Response({"detail": "Agent inactive"}, status=404)

        ser = AgentExecuteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        input_text = ser.validated_data["input"].strip()
        if not input_text:
            return Response({"detail": "input is required"}, status=400)
        session_uuid = ser.validated_data.get("session_uuid")
        options = ser.validated_data.get("options") or {}
        retrieval_overrides = ser.validated_data.get("retrieval_overrides") or {}

        # options merge: llm.extra < agent.config < request.options
        final_options = {**agent.llm.extra, **(agent.config or {}), **options}
        # RAG 用の retrieval パラメータは OpenAI/Ollama/Gemini チャット API には不要かつ
        # 送信すると 400 (invalid_request_error) を誘発するため除外する。
        retrieval_param_keys = {
            "datasource_ids",
            "top_k",
            "score_threshold",
            "embed_model",
            "retrieval_mode",
            "max_context_chars",
            "chunk_merge_strategy",
            "context_template",
            "citation_snippet_chars",
            "dedup_strategy",
        }
        chat_options_only = {
            k: v for k, v in final_options.items() if k not in retrieval_param_keys
        }

        # Session reuse or create
        session = None
        if session_uuid:
            try:
                session = ChatSession.objects.get(
                    uuid=session_uuid, is_active=True, agent=agent
                )
            except ChatSession.DoesNotExist:
                return Response({"detail": "Session not found"}, status=404)
        if session is None:
            session = ChatSession.objects.create(llm=agent.llm, agent=agent)

        # BASIC_CHAT と RAG_CHAT 分岐
        if agent.usecase_type == "RAG_CHAT":
            # system prompt 挿入 (一度だけ)
            if (
                agent.system_prompt
                and not session.messages.filter(role="system").exists()
            ):
                Message.objects.create(
                    session=session,
                    role="system",
                    content=agent.system_prompt,
                )
            # Retrieval + コンテキスト生成
            try:
                runner = RagChatRunner(
                    agent=agent,
                    session=session,
                    user_text=input_text,
                    overrides=retrieval_overrides,
                )
                rag_result: RagResult = runner.run()
            except ValueError as e:
                detail = str(e)
                if "datasource_ids" in detail:
                    return Response({"detail": detail}, status=422)
                if "context_template" in detail:
                    return Response({"detail": detail}, status=422)
                if "retrieval param invalid" in detail:
                    return Response({"detail": detail}, status=422)
                return Response({"detail": detail}, status=400)
            # RAG コンテキスト system メッセージ (都度追加)
            Message.objects.create(
                session=session,
                role="system",
                content=rag_result.content,
                metadata={"rag_context": True},
            )
            # User message (質問原文)
            Message.objects.create(
                session=session,
                role="user",
                content=input_text,
            )

            logger.debug(f"RAG_CHAT messages: {session}")

            messages = [
                {"role": m.role, "content": m.content} for m in session.messages.all()
            ]
            client = build_llm_client(agent.llm)

            chat_res = client.chat(messages, options=chat_options_only)
            assistant = Message.objects.create(
                session=session,
                role="assistant",
                content=chat_res.content,
                usage={**chat_res.usage, **rag_result.usage},
            )
            response = {
                "agent_id": agent.id,
                "session_uuid": str(session.uuid),
                "result": {
                    "message": {
                        "id": assistant.id,
                        "role": "assistant",
                        "content": assistant.content,
                    },
                    "citations": rag_result.citations,
                },
                "usage": assistant.usage,
            }
            return Response(response, status=200)

        # BASIC_CHAT 既存処理
        if agent.system_prompt and not session.messages.filter(role="system").exists():
            Message.objects.create(
                session=session,
                role="system",
                content=agent.system_prompt,
            )
        Message.objects.create(
            session=session,
            role="user",
            content=input_text,
        )
        messages = [
            {"role": m.role, "content": m.content} for m in session.messages.all()
        ]
        client = build_llm_client(agent.llm)
        result = client.chat(messages, options=chat_options_only)
        assistant = Message.objects.create(
            session=session,
            role="assistant",
            content=result.content,
            usage=result.usage,
        )
        response = {
            "agent_id": agent.id,
            "session_uuid": str(session.uuid),
            "result": {
                "message": {
                    "id": assistant.id,
                    "role": "assistant",
                    "content": assistant.content,
                }
            },
            "usage": result.usage,
        }
        return Response(response, status=200)


class DatasourceViewSet(viewsets.ModelViewSet):
    queryset = Datasource.objects.all()

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return DatasourceCreateUpdateSerializer
        return DatasourceSerializer

    def perform_destroy(self, instance):
        ds_id = instance.id
        super().perform_destroy(instance)
        # Chroma collection drop (best-effort, errors logged internally)
        drop_collection(ds_id)

    @action(detail=True, methods=["post", "get"], url_path="chunks")
    def chunks(self, request, pk=None):
        """POST: チャンク追加 / GET: チャンク一覧取得"""
        datasource = self.get_object()
        if not datasource.is_active:
            return Response({"detail": "Datasource inactive"}, status=404)
        if request.method.lower() == "get":
            # list
            try:
                limit = int(request.query_params.get("limit", 20))
                offset = int(request.query_params.get("offset", 0))
            except ValueError:
                return Response({"detail": "invalid limit/offset"}, status=400)
            try:
                data = list_chunks(datasource, limit=limit, offset=offset)
            except ValueError as e:
                return Response({"detail": str(e)}, status=400)
            except Exception:
                return Response({"detail": "failed to list chunks"}, status=500)
            return Response(data, status=200)
        # POST add chunk
        ser = DatasourceChunkCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        title = ser.validated_data["title"].strip()
        chunk_text = ser.validated_data["chunk_text"].strip()
        try:
            result = add_chunk(datasource, title, chunk_text)
        except EmbeddingError:
            return Response({"detail": "embedding generation failed"}, status=422)
        return Response(result, status=201)

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"chunks/(?P<chunk_id>[^/.]+)",
    )
    def delete_chunk_action(self, request, pk=None, chunk_id: str | None = None):
        datasource = self.get_object()
        if not datasource.is_active:
            return Response({"detail": "Datasource inactive"}, status=404)
        if not chunk_id:
            return Response({"detail": "chunk_id required"}, status=400)
        try:
            removed = delete_chunk(datasource, chunk_id)
        except Exception:
            return Response({"detail": "internal error"}, status=500)
        if not removed:
            return Response({"detail": "Chunk not found"}, status=404)
        return Response(status=204)
