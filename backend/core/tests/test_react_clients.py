from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from core.react_clients import open_react_client
from core.react_runner import ReActConfigurationError


class ReActClientTests(TestCase):
    def setUp(self):
        self.llm = SimpleNamespace(
            provider="OPENAI",
            is_active=True,
            api_key="unused-test-key",
            model="gpt-6-luna",
            base_url=None,
        )

    def test_explicit_base_url_wins_over_environment(self):
        self.llm.base_url = "https://example.invalid/v1"
        with (
            patch.dict(
                "os.environ", {"OPENAI_BASE_URL": "https://env.invalid/v1"}
            ),
            patch("core.react_clients.OpenAI") as factory,
        ):
            client = open_react_client(self.llm)
        self.assertIs(client, factory.return_value)
        factory.assert_called_once_with(
            api_key="unused-test-key",
            base_url="https://example.invalid/v1",
            timeout=30.0,
            max_retries=0,
        )

    def test_environment_and_default_base_url(self):
        for configured, expected in [
            ("https://env.invalid/v1", "https://env.invalid/v1"),
            ("", "https://api.openai.com/v1"),
        ]:
            with self.subTest(configured=configured):
                with (
                    patch.dict("os.environ", {"OPENAI_BASE_URL": configured}),
                    patch("core.react_clients.OpenAI") as factory,
                ):
                    open_react_client(self.llm)
                self.assertEqual(
                    factory.call_args.kwargs["base_url"], expected
                )

    def test_invalid_configuration_does_not_create_client(self):
        for field, value in [
            ("provider", "OLLAMA"),
            ("is_active", False),
            ("api_key", None),
            ("api_key", "  "),
            ("model", "  "),
        ]:
            with self.subTest(field=field, value=value):
                with (
                    patch.object(self.llm, field, value),
                    patch("core.react_clients.OpenAI") as factory,
                ):
                    with self.assertRaises(ReActConfigurationError):
                        open_react_client(self.llm)
                factory.assert_not_called()
