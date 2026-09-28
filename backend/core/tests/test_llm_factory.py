from django.test import TestCase

from core.models import LLM
from core.llm_clients import (
    build_llm_client,
    OllamaClient,
    OpenAIClient,
    GeminiClient,
)


class LLMFactoryTests(TestCase):
    def test_factory_returns_ollama_client(self):
        llm = LLM.objects.create(
            name="Local",
            provider="OLLAMA",
            model="llama3",
        )
        client = build_llm_client(llm)
        self.assertIsInstance(client, OllamaClient)

    def test_factory_returns_openai_client(self):
        llm = LLM.objects.create(
            name="OpenAI GPT",
            provider="OPENAI",
            model="gpt-4o-mini",
            api_key="sk-test",
        )
        client = build_llm_client(llm)
        self.assertIsInstance(client, OpenAIClient)

    def test_factory_returns_gemini_client(self):
        llm = LLM.objects.create(
            name="Gemini",
            provider="GEMINI",
            model="gemini-1.5-flash",
            api_key="gk-test",
        )
        client = build_llm_client(llm)
        self.assertIsInstance(client, GeminiClient)

    def test_factory_requires_api_key_openai(self):
        llm = LLM.objects.create(
            name="OpenAI no key",
            provider="OPENAI",
            model="gpt-4o-mini",
        )
        with self.assertRaises(ValueError):
            build_llm_client(llm)
