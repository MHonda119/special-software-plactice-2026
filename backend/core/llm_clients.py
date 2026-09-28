import os
import requests
import logging
from dataclasses import dataclass
from typing import Any


@dataclass
class ChatResult:
    content: str
    usage: dict


class BaseLLMClient:
    """共通インタフェース: chat(messages, options) -> ChatResult

    messages: list of {role, content}
    options: 追加パラメータ（温度など）。モデル保存時の extra をデフォルト値としてマージ。
    """

    def chat(
        self, messages: list[dict], options: dict | None = None
    ) -> ChatResult:  # pragma: no cover - interface
        raise NotImplementedError


class OllamaClient(BaseLLMClient):
    def __init__(
        self,
        base_url: str | None,
        model: str,
        default_params: dict | None = None,
    ):
        default_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        self.base_url = base_url or default_url
        self.model = model
        self.default_params = default_params or {}

    def chat(
        self,
        messages: list[dict],
        options: dict | None = None,
    ) -> ChatResult:
        url = self.base_url.rstrip("/") + "/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {**self.default_params, **(options or {})},
            "stream": False,
        }
        try:
            r = requests.post(
                url,
                json=payload,
                timeout=float(os.getenv("LLM_REQUEST_TIMEOUT", "60")),
            )
            r.raise_for_status()
            data = r.json()
        except requests.Timeout:
            logging.exception("Ollama request timeout")
            raise
        except requests.RequestException:
            logging.exception("Ollama request failed")
            raise
        content = data.get("message", {}).get("content", "")
        usage = {"eval_count": data.get("eval_count")}
        return ChatResult(content=content, usage=usage)


class OpenAIClient(BaseLLMClient):
    """OpenAI Chat Completions API クライアント (最小実装)。

    参考: https://platform.openai.com/docs/api-reference/chat/create
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None,
        model: str,
        default_params: dict | None = None,
    ):
        default_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.base_url = (base_url or default_url).rstrip("/")
        self.api_key = api_key
        self.model = model
        self.default_params = default_params or {}

    def chat(
        self,
        messages: list[dict],
        options: dict | None = None,
    ) -> ChatResult:
        url = self.base_url + "/chat/completions"
        merged = {**self.default_params, **(options or {})}
        # OpenAI Chat API に許可された代表的パラメータのみ送信し不要・未知キーを除外
        allowed_param_keys = {
            "temperature",
            "top_p",
            "n",
            "stream",
            "stop",
            "max_tokens",
            "presence_penalty",
            "frequency_penalty",
            "logit_bias",
            "user",
        }
        filtered = {k: v for k, v in merged.items() if k in allowed_param_keys}
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            **filtered,
        }
        # OpenAI は "stream" を False 明示不要（指定されたらそのまま送る）
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            r = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=float(os.getenv("LLM_REQUEST_TIMEOUT", "60")),
            )
            r.raise_for_status()
            data = r.json()
        except requests.Timeout:
            logging.exception("OpenAI request timeout")
            raise
        except requests.RequestException:
            logging.exception("OpenAI request failed")
            raise
        # Chat Completions 形式
        content = ""
        try:
            content = data["choices"][0]["message"].get("content") or ""
        except Exception:  # pragma: no cover - safety
            content = ""
        usage_raw = data.get("usage", {}) or {}
        # usage 正規化
        usage = {
            "prompt_tokens": usage_raw.get("prompt_tokens"),
            "completion_tokens": usage_raw.get("completion_tokens"),
            "total_tokens": usage_raw.get("total_tokens"),
        }
        return ChatResult(content=content, usage=usage)


class GeminiClient(BaseLLMClient):
    """Google Gemini generateContent API クライアント (最小実装)。

    参考: https://ai.google.dev/api/rest/v1beta/models.generateContent
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None,
        model: str,
        default_params: dict | None = None,
    ):
        # base_url 例: https://generativelanguage.googleapis.com
        default_url = os.getenv(
            "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com"
        )
        self.base_url = (base_url or default_url).rstrip("/")
        self.api_key = api_key
        self.model = model
        self.default_params = default_params or {}

    @staticmethod
    def _convert_messages(messages: list[dict]) -> list[dict]:
        """内部メッセージを Gemini contents 形式に変換。

        Gemini は role: user / model を想定。assistant -> model に変換。
        parts は text 単一。
        """
        converted: list[dict] = []
        for m in messages:
            role = m.get("role")
            if role == "assistant":
                role = "model"
            elif role not in ("user", "model", "system"):
                role = "user"
            # system メッセージは user として付与（簡易実装）
            if role == "system":
                role = "user"
            converted.append(
                {
                    "role": role,
                    "parts": [{"text": m.get("content", "")}],
                }
            )
        return converted

    def chat(
        self,
        messages: list[dict],
        options: dict | None = None,
    ) -> ChatResult:
        contents = self._convert_messages(messages)
        merged = {**self.default_params, **(options or {})}
        generation_config = {}
        # generationConfig に詰める代表的キーのみ抽出
        for k in ["temperature", "top_p", "top_k", "max_output_tokens"]:
            if k in merged:
                generation_config[k] = merged[k]
        payload: dict[str, Any] = {"contents": contents}
        if generation_config:
            payload["generationConfig"] = generation_config
        url = (
            f"{self.base_url}/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        try:
            r = requests.post(
                url,
                json=payload,
                timeout=float(os.getenv("LLM_REQUEST_TIMEOUT", "60")),
            )
            r.raise_for_status()
            data = r.json()
        except requests.Timeout:
            logging.exception("Gemini request timeout")
            raise
        except requests.RequestException:
            logging.exception("Gemini request failed")
            raise
        # content 抽出
        content = ""
        try:
            # candidates[0].content.parts[].text を連結
            parts = data["candidates"][0]["content"]["parts"]
            content = "".join(p.get("text", "") for p in parts)
        except Exception:  # pragma: no cover
            content = ""
        usage_meta = data.get("usageMetadata", {}) or {}
        usage = {
            "prompt_tokens": usage_meta.get("promptTokenCount"),
            "completion_tokens": usage_meta.get("candidatesTokenCount"),
            "total_tokens": usage_meta.get("totalTokenCount"),
        }
        return ChatResult(content=content, usage=usage)


def build_llm_client(llm) -> BaseLLMClient:
    provider = llm.provider.upper()
    if provider == "OPENAI":
        if not llm.api_key:
            raise ValueError("OPENAI provider requires api_key")
        return OpenAIClient(
            api_key=llm.api_key,
            base_url=llm.base_url,
            model=llm.model,
            default_params=llm.extra,
        )
    if provider == "GEMINI":
        if not llm.api_key:
            raise ValueError("GEMINI provider requires api_key")
        return GeminiClient(
            api_key=llm.api_key,
            base_url=llm.base_url,
            model=llm.model,
            default_params=llm.extra,
        )
    # default OLLAMA
    return OllamaClient(llm.base_url, llm.model, llm.extra)
