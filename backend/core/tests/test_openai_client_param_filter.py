from django.test import SimpleTestCase
from core.llm_clients import OpenAIClient


class OpenAIClientParamFilterTests(SimpleTestCase):
    def test_extraneous_params_are_filtered(self):
        # Arrange: build client with dummy credentials
        client = OpenAIClient(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-5-chat-latest",
        )
        messages = [{"role": "user", "content": "hello"}]
        options = {
            "temperature": 0.2,
            "datasource_ids": [1],  # invalid for chat
            "embed_model": "text-embedding-3-small",  # invalid for chat
            "max_context_chars": 1000,  # invalid for chat
        }

        captured_payload = {}

        def fake_post(url, json, headers=None, timeout=None):  # noqa: D401
            class DummyResponse:
                def __init__(self, data):
                    self._data = data
                    self.status_code = 200

                def raise_for_status(self):
                    return None

                def json(self):
                    return {
                        "choices": [{"message": {"content": "ok"}}],
                        "usage": {
                            "prompt_tokens": 1,
                            "completion_tokens": 1,
                            "total_tokens": 2,
                        },
                    }

            captured_payload.update(json)
            return DummyResponse(json)

        # Monkeypatch requests.post
        import requests

        original_post = requests.post
        requests.post = fake_post  # type: ignore
        try:
            client.chat(messages, options=options)
        finally:
            requests.post = original_post  # restore

        # Assert
        assert "datasource_ids" not in captured_payload
        assert "embed_model" not in captured_payload
        assert "max_context_chars" not in captured_payload
        assert "temperature" in captured_payload
        assert captured_payload["model"] == "gpt-5-chat-latest"
        assert captured_payload["messages"] == messages
