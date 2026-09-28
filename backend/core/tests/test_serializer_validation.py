from django.test import TestCase

from core.serializers import LLMCreateUpdateSerializer


class LLMSerializerValidationTests(TestCase):
    def test_openai_requires_api_key(self):
        serializer = LLMCreateUpdateSerializer(
            data={
                "name": "OpenAI GPT",
                "provider": "OPENAI",
                "model": "gpt-4o-mini",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("api_key", serializer.errors)

    def test_openai_with_api_key_valid(self):
        serializer = LLMCreateUpdateSerializer(
            data={
                "name": "OpenAI GPT",
                "provider": "OPENAI",
                "model": "gpt-4o-mini",
                "api_key": "sk-test",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_ollama_without_api_key_valid(self):
        serializer = LLMCreateUpdateSerializer(
            data={
                "name": "Local",
                "provider": "OLLAMA",
                "model": "llama3",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
