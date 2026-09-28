import logging
from dataclasses import dataclass
from typing import Any, List, Dict

from .models import Agent, ChatSession, Datasource
from .datasource_store import (
    get_chroma_client,
    collection_name,
    generate_embedding,
)


@dataclass
class RagResult:
    content: str
    citations: list[dict]
    usage: dict


class RagChatRunner:
    """RAG_CHAT 実行ロジック (単純類似検索 + コンテキスト挿入)。"""

    def __init__(
        self,
        agent: Agent,
        session: ChatSession | None,
        user_text: str,
        overrides: dict | None,
    ):
        self.agent = agent
        self.session = session
        self.user_text = user_text
        self.overrides = overrides or {}
        self.config = {**(agent.config or {})}
        # retrieval_overrides のキーのみ上書き
        for k, v in self.overrides.items() if self.overrides else []:
            if k in {
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
            }:
                self.config[k] = v

    def _validate_config(self) -> tuple[list[int], dict]:
        ds_ids = self.config.get("datasource_ids") or []
        if not ds_ids:
            raise ValueError("datasource_ids required")
        top_k = int(self.config.get("top_k", 5))
        if top_k < 1 or top_k > 100:
            raise ValueError("retrieval param invalid: top_k")
        template = self.config.get(
            "context_template",
            (
                "You are a RAG assistant.\n"
                "Relevant Info:\n"
                "{{chunks}}\n"
                "User: {{question}}"
            ),
        )
        if "{{chunks}}" not in template or "{{question}}" not in template:
            raise ValueError("context_template placeholders missing")
        params = {
            "top_k": top_k,
            "score_threshold": float(self.config.get("score_threshold", 0.0)),
            "embed_model": self.config.get("embed_model"),
            "retrieval_mode": self.config.get("retrieval_mode", "UNION"),
            "max_context_chars": int(self.config.get("max_context_chars", 8000)),
            "chunk_merge_strategy": self.config.get(
                "chunk_merge_strategy",
                "NEWLINE",
            ),
            "context_template": template,
            "citation_snippet_chars": int(
                self.config.get("citation_snippet_chars", 200)
            ),
            "dedup_strategy": self.config.get("dedup_strategy", "NONE"),
        }
        return ds_ids, params

    @staticmethod
    def _format_chunk(hit: dict, strategy: str) -> str:
        title = hit.get("title") or ""
        text = hit.get("text") or ""
        if strategy == "TITLE_PREFIX" and title:
            return f"[ {title} ]\n{text}"
        return text

    @staticmethod
    def _score_from_distance(dist: float) -> float:
        # Chroma の距離が cosine 距離を想定し 1-dist でスコア化
        try:
            if dist < 0:
                return 0.0
            if dist > 1:
                # 不正値は正規化 (上限 1.0 未満に丸め)
                return max(0.0, 1.0 - (dist - 1.0))
            return 1.0 - dist
        except Exception:
            return 0.0

    def _embed_query(
        self,
        text: str,
        model_override: str | None,
    ) -> list[float]:
        """ユーザクエリを埋め込みベクトルへ変換する。
        retrieval_overrides / agent.config に `embed_model`に指定されている
        Embedding用モデルをRetrieve時に利用する。
        datasource_storeのgenerate_embedding関数は`Datasource` オブジェクトのLLM を
        デフォで参照するため、永続化しない擬似 Datasource を
        ModelOverride(対話用モデルを埋め込みモデルで上書き)生成して渡す。
        """
        llm = self.agent.llm
        selected_model = model_override  # 明示的に選択
        # 擬似 Datasource: llm 参照のみ (DB 未保存)
        pseudo_ds = Datasource(llm=llm)
        return generate_embedding(
            text,
            pseudo_ds,
            model_override=(selected_model if selected_model != llm.model else None),
        )  # type: ignore[arg-type]

    def run(self) -> RagResult:
        ds_ids, params = self._validate_config()
        query_vec = self._embed_query(self.user_text, params["embed_model"])
        client = get_chroma_client()
        all_hits: List[Dict[str, Any]] = []
        for ds_id in ds_ids:
            try:
                coll = client.get_collection(collection_name(ds_id))
            except Exception:
                # コレクションが無ければスキップ (空扱い)
                continue
            try:
                q = coll.query(
                    query_embeddings=[query_vec],
                    n_results=params["top_k"],
                )
            except Exception:
                logging.exception(
                    "vector store query failed for datasource=%s",
                    ds_id,
                )
                continue
            ids = q.get("ids", [[]])[0]
            docs = q.get("documents", [[]])[0]
            metas = q.get("metadatas", [[]])[0]
            dists = q.get("distances", [[]])[0] or []
            for i, cid in enumerate(ids):
                score = self._score_from_distance(dists[i] if i < len(dists) else 1.0)
                if score < params["score_threshold"]:
                    continue
                all_hits.append(
                    {
                        "datasource_id": ds_id,
                        "chunk_id": cid,
                        "text": docs[i] if i < len(docs) else "",
                        "title": (metas[i].get("title") if i < len(metas) else None),
                        "score": score,
                    }
                )
        if params["retrieval_mode"] == "MERGE_RANK":
            all_hits.sort(key=lambda h: h["score"], reverse=True)
        # dedup
        if params["dedup_strategy"] == "HASH_EXACT":
            seen = set()
            deduped = []
            for h in all_hits:
                key = hash(h.get("text") or "")
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(h)
            all_hits = deduped
        # コンテキスト構築
        merged_chunks: List[str] = [
            self._format_chunk(
                h,
                params["chunk_merge_strategy"],
            )
            for h in all_hits
        ]
        context_raw = "\n".join(merged_chunks)
        if len(context_raw) > params["max_context_chars"]:
            context_raw = context_raw[: params["max_context_chars"]] + "..."
        context_message = (
            params["context_template"]
            .replace("{{chunks}}", context_raw)
            .replace("{{question}}", self.user_text)
        )
        # citations 整形
        citations = []
        for rank, h in enumerate(all_hits, start=1):
            snippet_len = params["citation_snippet_chars"]
            text = h.get("text") or ""
            citations.append(
                {
                    "datasource_id": h["datasource_id"],
                    "chunk_id": h["chunk_id"],
                    "title": h.get("title"),
                    "score": round(h.get("score", 0.0), 4),
                    "rank": rank,
                    "snippet": (
                        text[:snippet_len] + ("..." if len(text) > snippet_len else "")
                    ),
                }
            )
        usage = {
            "retrieval": {
                "datasources": ds_ids,
                "total_candidates": len(all_hits),
                "used_chunks": len(all_hits),
                "top_k_requested": params["top_k"],
            }
        }
        return RagResult(
            content=context_message,
            citations=citations,
            usage=usage,
        )
