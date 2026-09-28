import os
import uuid
import logging
from typing import Any

import requests
import chromadb
from chromadb.api.types import Embedding

from .models import Datasource

_CHROMA_CLIENT = None


def get_chroma_client():
    global _CHROMA_CLIENT
    if _CHROMA_CLIENT is None:
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "/data/chroma")
        try:
            _CHROMA_CLIENT = chromadb.PersistentClient(path=persist_dir)
        except Exception:  # pragma: no cover - init failure
            logging.exception("Failed to init chroma client")
            raise
    return _CHROMA_CLIENT


def collection_name(datasource_id: int) -> str:
    return f"datasource_{datasource_id}"  # 名前規則固定


def get_or_create_collection(datasource_id: int):
    client = get_chroma_client()
    name = collection_name(datasource_id)
    try:
        coll = client.get_collection(name=name)
    except Exception:
        coll = client.create_collection(name=name)
    return coll


def drop_collection(datasource_id: int):
    client = get_chroma_client()
    name = collection_name(datasource_id)
    try:
        client.delete_collection(name=name)
    except Exception:  # 無ければ無視
        logging.info("Chroma collection %s not found on drop", name)


class EmbeddingError(Exception):
    pass


def generate_embedding(
    text: str, datasource: Datasource, model_override: str | None = None
) -> Embedding:
    """埋め込み生成 (OLLAMA / OPENAI 対応)。

    OPENAI: https://platform.openai.com/docs/api-reference/embeddings
        POST /embeddings {"model": <model>, "input": <text>}
        -> data[0].embedding
    OLLAMA: POST /api/embeddings {"model": <model>, "prompt": <text>}
        -> embedding
    """
    llm = datasource.llm
    provider = llm.provider.upper()
    # Datasource から埋め込み専用モデルを選択する仕様を廃止し llm.model を常用。
    # retrieval オーバーライドで一時的に別モデルを利用したい場合 model_override を使用。
    model = model_override or llm.model

    if provider == "OPENAI":
        if not llm.api_key:
            raise EmbeddingError("embedding generation failed: missing api_key")
        base_url = (
            llm.base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        url = base_url + "/embeddings"
        payload = {"model": model, "input": text}
        headers = {
            "Authorization": f"Bearer {llm.api_key}",
            "Content-Type": "application/json",
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=30)
            r.raise_for_status()
            data: dict[str, Any] = r.json()
            emb = None
            if isinstance(data.get("data"), list) and data["data"]:
                emb = data["data"][0].get("embedding")
            if not isinstance(emb, list):
                raise EmbeddingError("embedding generation failed")
            return emb  # type: ignore
        except requests.RequestException:
            logging.exception("OpenAI embedding request failed")
            raise EmbeddingError("embedding generation failed")

    if provider == "OLLAMA":
        base_url = llm.base_url or os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        url = base_url.rstrip("/") + "/api/embeddings"
        payload = {"model": model, "prompt": text}
        try:
            r = requests.post(url, json=payload, timeout=30)
            r.raise_for_status()
            data: dict[str, Any] = r.json()
            emb = data.get("embedding")
            if not isinstance(emb, list):
                raise EmbeddingError("embedding generation failed")
            return emb  # type: ignore
        except requests.RequestException:
            logging.exception("Ollama embedding request failed")
            raise EmbeddingError("embedding generation failed")

    raise EmbeddingError("embedding generation failed: unsupported provider")


def add_chunk(datasource: Datasource, title: str, chunk_text: str) -> dict[str, Any]:
    """チャンクを埋め込み生成して Chroma に追加し結果メタ情報を返す。"""
    embedding = generate_embedding(chunk_text, datasource)
    coll = get_or_create_collection(datasource.id)
    chunk_id = str(uuid.uuid4())
    coll.add(
        ids=[chunk_id],
        metadatas=[{"title": title}],
        documents=[chunk_text],
        embeddings=[embedding],
    )
    return {
        "datasource_id": datasource.id,
        "chunk_id": chunk_id,
        "title": title,
        "text_length": len(chunk_text),
    }


def list_chunks(
    datasource: Datasource, limit: int = 20, offset: int = 0
) -> dict[str, Any]:
    """Chroma コレクションからチャンク一覧を取得 (メタ + 長さ)。

    コレクションが存在しない場合は空配列を返す。
    """
    if limit < 1 or limit > 100:
        raise ValueError("limit out of range")
    if offset < 0:
        raise ValueError("offset out of range")
    client = get_chroma_client()
    name = collection_name(datasource.id)
    try:
        coll = client.get_collection(name=name)
    except Exception:
        return {
            "datasource_id": datasource.id,
            "count": 0,
            "limit": limit,
            "offset": offset,
            "chunks": [],
        }
    try:
        result = coll.get(limit=limit, offset=offset)
    except Exception:
        logging.exception("failed to list chunks: datasource=%s", datasource.id)
        raise
    ids = result.get("ids", []) or []
    docs = result.get("documents", []) or []
    metas = result.get("metadatas", []) or []
    chunks: list[dict[str, Any]] = []
    for i, cid in enumerate(ids):
        title = None
        if i < len(metas) and isinstance(metas[i], dict):
            title = metas[i].get("title")
        text = docs[i] if i < len(docs) else ""
        chunks.append(
            {
                "chunk_id": cid,
                "title": title,
                "text_length": len(text),
            }
        )
    return {
        "datasource_id": datasource.id,
        "count": len(chunks),
        "limit": limit,
        "offset": offset,
        "chunks": chunks,
    }


def delete_chunk(datasource: Datasource, chunk_id: str) -> bool:
    """指定チャンク ID を削除。存在しなければ False。

    エラー時は例外伝播。
    """
    client = get_chroma_client()
    name = collection_name(datasource.id)
    try:
        coll = client.get_collection(name=name)
    except Exception:
        return False  # コレクション自体が無ければ chunk は存在しない
    try:
        got = coll.get(ids=[chunk_id])
    except Exception:
        logging.exception(
            "failed to get chunk before delete: datasource=%s", datasource.id
        )
        return False
    ids = got.get("ids", []) or []
    if not ids:
        return False
    try:
        coll.delete(ids=[chunk_id])
    except Exception:
        logging.exception(
            "failed to delete chunk: datasource=%s chunk=%s",
            datasource.id,
            chunk_id,
        )
        raise
    return True
