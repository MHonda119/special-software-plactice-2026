import os

from openai import OpenAI

from .react_runner import ReActConfigurationError


def open_react_client(llm):
    if not llm.is_active or llm.provider != "OPENAI":
        raise ReActConfigurationError("有効な OPENAI の LLM を指定してください。")
    if not llm.api_key or not llm.api_key.strip() or not llm.model.strip():
        raise ReActConfigurationError("API キーとモデル名を設定してください。")
    return OpenAI(
        api_key=llm.api_key,
        base_url=(
            llm.base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        ),
        timeout=30.0,
        max_retries=0,
    )
