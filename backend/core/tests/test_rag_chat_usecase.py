import os
from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient
from core.models import LLM, Agent, Datasource
from core.llm_clients import ChatResult


class RagChatUsecaseTests(TestCase):
    def setUp(self):  # noqa: D401
        self.client = APIClient()
        os.environ["CHROMA_PERSIST_DIR"] = "/tmp/chroma_test"
        self.llm = LLM.objects.create(
            name="Local",
            provider="OLLAMA",
            model="nomic-embed-text",
            extra={"temperature": 0.2},
        )
        self.chat_llm = LLM.objects.create(
            name="Chat",
            provider="OLLAMA",
            model="llama3",
            extra={"temperature": 0.2, "max_tokens": 100},
        )

    def fake_client_factory(self, *args, **kwargs):  # noqa: D401
        class Dummy:
            def chat(self_inner, messages, options=None):  # noqa: D401
                # system メッセージ数を含む決定的なレスポンス
                sys_count = sum(1 for m in messages if m["role"] == "system")
                return ChatResult(
                    content=f"SYS={sys_count}; ANSWER",
                    usage={"eval_count": 1},
                )

        return Dummy()

    def _add_chunk(self, ds: Datasource, title: str, text: str):  # helper
        with patch(
            "core.datasource_store.generate_embedding",
            return_value=[0.1, 0.2, 0.3],
        ):
            r = self.client.post(
                f"/api/datasources/{ds.id}/chunks/",
                {"title": title, "chunk_text": text},
                format="json",
            )
        self.assertEqual(r.status_code, 201, r.content)
        return r.data

    def test_execute_rag_chat_success(self):
        ds = Datasource.objects.create(name="Docs", llm=self.llm)
        self._add_chunk(ds, "Intro", "RAG 概要説明テキスト")
        agent = Agent.objects.create(
            name="RagAgent",
            usecase_type="RAG_CHAT",
            llm=self.chat_llm,
            system_prompt="You are helpful.",
            config={
                "datasource_ids": [ds.id],
                "top_k": 3,
                "citation_snippet_chars": 50,
            },
        )
        with patch("core.views.build_llm_client", self.fake_client_factory), patch(
            "core.rag_runner.generate_embedding", return_value=[0.1, 0.2, 0.3]
        ):
            r = self.client.post(
                f"/api/agents/{agent.id}/execute/",
                {"input": "RAG とは?"},
                format="json",
            )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("citations", r.data["result"])
        self.assertGreaterEqual(len(r.data["result"]["citations"]), 1)
        # usage 結合 (retrieval 情報含む)
        self.assertIn("retrieval", r.data["usage"])

    def test_execute_missing_datasource_ids(self):
        agent = Agent.objects.create(
            name="RagBad",
            usecase_type="RAG_CHAT",
            llm=self.chat_llm,
            config={},  # datasource_ids 無し
        )
        with patch("core.views.build_llm_client", self.fake_client_factory), patch(
            "core.rag_runner.generate_embedding", return_value=[0.1, 0.2, 0.3]
        ):
            r = self.client.post(
                f"/api/agents/{agent.id}/execute/",
                {"input": "Ping"},
                format="json",
            )
        self.assertEqual(r.status_code, 422)
        self.assertIn(b"datasource_ids required", r.content)

    def test_execute_context_template_placeholder_missing(self):
        ds = Datasource.objects.create(name="Docs", llm=self.llm)
        self._add_chunk(ds, "Intro", "テキスト A")
        agent = Agent.objects.create(
            name="RagInvalidTpl",
            usecase_type="RAG_CHAT",
            llm=self.chat_llm,
            config={"datasource_ids": [ds.id], "context_template": "NO VARS"},
        )
        with patch("core.views.build_llm_client", self.fake_client_factory), patch(
            "core.rag_runner.generate_embedding", return_value=[0.1, 0.2, 0.3]
        ):
            r = self.client.post(
                f"/api/agents/{agent.id}/execute/",
                {"input": "Q"},
                format="json",
            )
        self.assertEqual(r.status_code, 422)
        self.assertIn(b"context_template", r.content)

    def test_citation_snippet_truncation(self):
        ds = Datasource.objects.create(name="Docs", llm=self.llm)
        long_text = "あ" * 30
        self._add_chunk(ds, "Long", long_text)
        agent = Agent.objects.create(
            name="RagSnippet",
            usecase_type="RAG_CHAT",
            llm=self.chat_llm,
            config={
                "datasource_ids": [ds.id],
                "citation_snippet_chars": 5,
            },
        )
        with patch("core.views.build_llm_client", self.fake_client_factory), patch(
            "core.rag_runner.generate_embedding", return_value=[0.1, 0.2, 0.3]
        ):
            r = self.client.post(
                f"/api/agents/{agent.id}/execute/",
                {"input": "Q"},
                format="json",
            )
        self.assertEqual(r.status_code, 200, r.content)
        snippet = r.data["result"]["citations"][0]["snippet"]
        self.assertTrue(snippet.endswith("..."))

    def test_top_k_override(self):
        ds = Datasource.objects.create(name="Docs", llm=self.llm)
        self._add_chunk(ds, "A", "テキスト1")
        self._add_chunk(ds, "B", "テキスト2")
        agent = Agent.objects.create(
            name="RagTopK",
            usecase_type="RAG_CHAT",
            llm=self.chat_llm,
            config={"datasource_ids": [ds.id], "top_k": 5},
        )
        with patch("core.views.build_llm_client", self.fake_client_factory), patch(
            "core.rag_runner.generate_embedding", return_value=[0.1, 0.2, 0.3]
        ):
            r = self.client.post(
                f"/api/agents/{agent.id}/execute/",
                {"input": "Q", "retrieval_overrides": {"top_k": 1}},
                format="json",
            )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data["result"]["citations"]), 1)
