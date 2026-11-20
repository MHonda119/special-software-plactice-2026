import json
from unittest.mock import patch

import httpx
from django.contrib.auth import get_user_model
from django.test import TestCase
from openai import OpenAI
from rest_framework.test import APIClient

from core.models import Agent, ChatSession, LLM


def sdk_tool_call(name, arguments, call_id):
    return [
        {
            "type": "function_call",
            "id": "fc_" + call_id,
            "call_id": call_id,
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False),
            "status": "completed",
        }
    ]


def sdk_answer(text):
    return [
        {
            "type": "message",
            "id": "msg_final",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }
    ]


class ReActSdkTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(get_user_model().objects.create_user("student"))
        self.llm = LLM.objects.create(
            name="GPT-6 luna",
            provider="OPENAI",
            model="gpt-6-luna",
            api_key="unused-test-key",
            base_url="https://example.invalid/v1",
        )
        self.agent = Agent.objects.create(
            name="ReAct",
            usecase_type="REACT_CHAT",
            llm=self.llm,
            system_prompt="講義用の商品について回答する。",
        )
        self.url = f"/api/agents/{self.agent.id}/execute/"

    def test_real_sdk_runs_tools_and_reuses_history_across_two_turns(self):
        outputs = iter(
            [
                sdk_tool_call("get_product_price", {"product": "ノート"}, "price-1"),
                sdk_tool_call(
                    "calculate",
                    {"operation": "multiply", "left": 250, "right": 3},
                    "multiply-1",
                ),
                sdk_tool_call(
                    "calculate",
                    {"operation": "subtract", "left": 1000, "right": 750},
                    "subtract-1",
                ),
                sdk_answer("お釣りは250円です。"),
                sdk_tool_call("get_product_price", {"product": "ペン"}, "price-2"),
                sdk_tool_call(
                    "calculate",
                    {"operation": "multiply", "left": 120, "right": 2},
                    "multiply-2",
                ),
                sdk_tool_call(
                    "calculate",
                    {"operation": "subtract", "left": 500, "right": 240},
                    "subtract-2",
                ),
                sdk_answer("お釣りは260円です。"),
            ]
        )
        requests = []
        clients = []

        def handle(request):
            self.assertEqual(str(request.url), "https://example.invalid/v1/responses")
            self.assertEqual(request.method, "POST")
            requests.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "id": "resp_test",
                    "object": "response",
                    "created_at": 0,
                    "model": "gpt-6-luna",
                    "status": "completed",
                    "output": next(outputs),
                    "usage": {
                        "input_tokens": 2,
                        "output_tokens": 1,
                        "total_tokens": 3,
                    },
                },
            )

        def factory(llm):
            client = OpenAI(
                api_key=llm.api_key,
                base_url=llm.base_url,
                max_retries=0,
                http_client=httpx.Client(transport=httpx.MockTransport(handle)),
            )
            clients.append(client)
            return client

        with patch("core.views.open_react_client", side_effect=factory):
            first = self.client.post(
                self.url,
                {"input": "ノート3冊を買って1000円払うと？"},
                format="json",
            )
            self.assertEqual(first.status_code, 200, first.data)
            second = self.client.post(
                self.url,
                {
                    "input": "ではペン2本を買って500円なら？",
                    "session_uuid": first.data["session_uuid"],
                },
                format="json",
            )

        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(
            first.data["result"]["message"]["content"], "お釣りは250円です。"
        )
        self.assertEqual(
            second.data["result"]["message"]["content"], "お釣りは260円です。"
        )
        self.assertEqual(second.data["session_uuid"], first.data["session_uuid"])
        self.assertEqual(second.data["usage"]["total_tokens"], 12)
        self.assertEqual(len(requests), 8)
        self.assertEqual(requests[0]["model"], "gpt-6-luna")
        self.assertIn(self.agent.system_prompt, requests[0]["instructions"])
        self.assertEqual(
            requests[4]["input"],
            [
                {"role": "user", "content": "ノート3冊を買って1000円払うと？"},
                {"role": "assistant", "content": "お釣りは250円です。"},
                {"role": "user", "content": "ではペン2本を買って500円なら？"},
            ],
        )
        observation = requests[3]["input"][-1]
        self.assertEqual(observation["call_id"], "subtract-1")
        self.assertEqual(json.loads(observation["output"]), {"result": 250})
        session = ChatSession.objects.get(uuid=first.data["session_uuid"])
        self.assertEqual(self.agent.sessions.count(), 1)
        self.assertEqual(
            list(session.messages.values_list("role", flat=True)),
            ["user", "assistant", "user", "assistant"],
        )
        self.assertTrue(all(client.is_closed() for client in clients))

    def test_real_sdk_errors_are_sanitized_without_saving_or_retrying(self):
        for status_code in [401, 429, 500]:
            with self.subTest(status_code=status_code):
                requests = []

                def handle(request):
                    requests.append(request)
                    return httpx.Response(
                        status_code,
                        json={
                            "error": {"message": "private-provider-detail"},
                        },
                    )

                sdk_client = OpenAI(
                    api_key="unused-test-key",
                    base_url="https://example.invalid/v1",
                    max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(handle)),
                )
                with patch("core.views.open_react_client", return_value=sdk_client):
                    result = self.client.post(
                        self.url, {"input": "質問"}, format="json"
                    )

                self.assertEqual(result.status_code, 502)
                self.assertEqual(result.data, {"detail": "ReAct execution failed"})
                self.assertEqual(self.agent.sessions.count(), 0)
                self.assertEqual(len(requests), 1)
                self.assertTrue(sdk_client.is_closed())
