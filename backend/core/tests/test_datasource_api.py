from unittest.mock import patch
import os
import uuid
from django.test import TestCase
from rest_framework.test import APIClient
from core.models import LLM, Datasource
from core.datasource_store import EmbeddingError
import core.datasource_store as ds_store


class DatasourceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # テスト毎に分離された Chroma 永続ディレクトリを使用しデータ汚染回避
        self.persist_dir = f"/tmp/chroma_test_{uuid.uuid4()}"
        os.environ["CHROMA_PERSIST_DIR"] = self.persist_dir
        ds_store._CHROMA_CLIENT = None  # グローバルクライアントリセット
        self.llm = LLM.objects.create(
            name="Local",
            provider="OLLAMA",
            model="nomic-embed-text",
        )

    def test_create_success(self):
        payload = {
            "name": "Docs A",
            "description": "社内ナレッジ",
            "llm": self.llm.id,
        }
        r = self.client.post("/api/datasources/", payload, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["name"], "Docs A")

    def test_create_name_required(self):
        payload = {"name": "", "llm": self.llm.id}
        r = self.client.post("/api/datasources/", payload, format="json")
        self.assertEqual(r.status_code, 400)

    def test_add_chunk_success(self):
        ds = Datasource.objects.create(name="DS", llm=self.llm)
        with patch(
            "core.datasource_store.generate_embedding",
            return_value=[0.1, 0.2, 0.3],
        ):
            r = self.client.post(
                f"/api/datasources/{ds.id}/chunks/",
                {
                    "title": "RAG",
                    "chunk_text": "RAG は Retrieval Augmented Generation",
                },
                format="json",
            )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["datasource_id"], ds.id)
        self.assertTrue("chunk_id" in r.data)
        self.assertEqual(r.data["title"], "RAG")

    def test_list_chunks_empty(self):
        ds = Datasource.objects.create(name="Empty", llm=self.llm)
        r = self.client.get(f"/api/datasources/{ds.id}/chunks/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["datasource_id"], ds.id)
        self.assertEqual(r.data["count"], 0)
        self.assertEqual(r.data["chunks"], [])

    def _add_chunk(self, ds: Datasource, title: str, text: str):  # helper
        with patch(
            "core.datasource_store.generate_embedding",
            return_value=[0.1, 0.2, 0.3],
        ):
            return self.client.post(
                f"/api/datasources/{ds.id}/chunks/",
                {"title": title, "chunk_text": text},
                format="json",
            )

    def test_list_chunks_with_data(self):
        ds = Datasource.objects.create(name="WithData", llm=self.llm)
        self._add_chunk(ds, "A", "TEXT A")
        self._add_chunk(ds, "B", "TEXT BBB")
        r = self.client.get(f"/api/datasources/{ds.id}/chunks/?limit=10&offset=0")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["count"], 2)
        ids = [c["chunk_id"] for c in r.data["chunks"]]
        self.assertEqual(len(ids), 2)

    def test_delete_chunk_success(self):
        ds = Datasource.objects.create(name="Del", llm=self.llm)
        add_res = self._add_chunk(ds, "A", "TEXT A")
        cid = add_res.data["chunk_id"]
        r = self.client.delete(
            f"/api/datasources/{ds.id}/chunks/{cid}/",
            format="json",
        )
        self.assertEqual(r.status_code, 204, r.content)
        # 再一覧で空
        list_res = self.client.get(f"/api/datasources/{ds.id}/chunks/")
        self.assertEqual(list_res.data["count"], 0)

    def test_delete_chunk_not_found(self):
        ds = Datasource.objects.create(name="DelNF", llm=self.llm)
        r = self.client.delete(
            f"/api/datasources/{ds.id}/chunks/NOPE-123/",
            format="json",
        )
        self.assertEqual(r.status_code, 404)
        self.assertIn(b"Chunk not found", r.content)

    def test_list_chunks_inactive_datasource(self):
        ds = Datasource.objects.create(name="Inactive", llm=self.llm, is_active=False)
        r = self.client.get(f"/api/datasources/{ds.id}/chunks/")
        self.assertEqual(r.status_code, 404)

    def test_delete_chunk_inactive_datasource(self):
        ds = Datasource.objects.create(
            name="InactiveDel", llm=self.llm, is_active=False
        )
        r = self.client.delete(
            f"/api/datasources/{ds.id}/chunks/ANY/",
            format="json",
        )
        self.assertEqual(r.status_code, 404)

    def test_add_chunk_validation_error(self):
        ds = Datasource.objects.create(name="DS", llm=self.llm)
        r = self.client.post(
            f"/api/datasources/{ds.id}/chunks/",
            {"title": "", "chunk_text": ""},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_add_chunk_inactive_datasource(self):
        ds = Datasource.objects.create(name="DS", llm=self.llm, is_active=False)
        r = self.client.post(
            f"/api/datasources/{ds.id}/chunks/",
            {"title": "A", "chunk_text": "B"},
            format="json",
        )
        self.assertEqual(r.status_code, 404)

    def test_embedding_failure_returns_422(self):
        ds = Datasource.objects.create(name="DS", llm=self.llm)

        def raise_error(*args, **kwargs):  # noqa: D401 - stub
            raise EmbeddingError("embedding generation failed")

        with patch("core.datasource_store.generate_embedding", raise_error):
            r = self.client.post(
                f"/api/datasources/{ds.id}/chunks/",
                {"title": "RAG", "chunk_text": "text"},
                format="json",
            )
        self.assertEqual(r.status_code, 422)
        self.assertIn(b"embedding generation failed", r.content)

    def test_add_chunk_success_openai(self):
        openai_llm = LLM.objects.create(
            name="OpenAI LLM",
            provider="OPENAI",
            model="text-embedding-3-small",
            api_key="sk-test",
        )
        ds = Datasource.objects.create(name="ODS", llm=openai_llm)

        class DummyResp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"data": [{"embedding": [0.11, 0.22, 0.33]}]}

        with patch("core.datasource_store.requests.post", return_value=DummyResp()):
            r = self.client.post(
                f"/api/datasources/{ds.id}/chunks/",
                {"title": "Intro", "chunk_text": "Embedding API"},
                format="json",
            )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["datasource_id"], ds.id)
        self.assertTrue("chunk_id" in r.data)

    def test_openai_missing_api_key_returns_422(self):
        openai_llm = LLM.objects.create(
            name="OpenAI NoKey",
            provider="OPENAI",
            model="text-embedding-3-small",
        )
        ds = Datasource.objects.create(name="ODS", llm=openai_llm)
        r = self.client.post(
            f"/api/datasources/{ds.id}/chunks/",
            {"title": "T", "chunk_text": "X"},
            format="json",
        )
        self.assertEqual(r.status_code, 422)
        self.assertIn(b"embedding generation failed", r.content)
