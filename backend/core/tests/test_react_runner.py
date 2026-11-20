import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from core.react_runner import (
    INSTRUCTIONS,
    ReActConfigurationError,
    ReActError,
    ReActLimitError,
    ReActRunner,
)
from core.react_tools import execute_tool


def tool_call(name, arguments, call_id):
    return SimpleNamespace(
        type="function_call",
        name=name,
        arguments=json.dumps(arguments, ensure_ascii=False),
        call_id=call_id,
    )


def response(output=None, text="", status="completed"):
    return SimpleNamespace(
        status=status,
        output=output or [],
        output_text=text,
        usage=SimpleNamespace(input_tokens=2, output_tokens=1, total_tokens=3),
    )


class ReActRunnerTests(TestCase):
    def test_four_steps_keep_outputs_and_call_ids(self):
        client = Mock()
        marker = SimpleNamespace(type="reasoning")
        client.responses.create.side_effect = [
            response(
                [
                    marker,
                    tool_call("get_product_price", {"product": "ノート"}, "price-1"),
                ]
            ),
            response(
                [
                    tool_call(
                        "calculate",
                        {"operation": "multiply", "left": 250, "right": 3},
                        "math-1",
                    )
                ]
            ),
            response(
                [
                    tool_call(
                        "calculate",
                        {"operation": "subtract", "left": 1000, "right": 750},
                        "math-2",
                    )
                ]
            ),
            response(text="お釣りは250円です。"),
        ]
        messages = [{"role": "user", "content": "ノート3冊のお釣りは？"}]

        result = ReActRunner(client, "gpt-6-luna", max_steps=4).run(messages)

        self.assertEqual(result.content, "お釣りは250円です。")
        self.assertEqual(result.usage["total_tokens"], 12)
        self.assertEqual(len(messages), 1)
        self.assertEqual(client.responses.create.call_count, 4)
        last_input = client.responses.create.call_args.kwargs["input"]
        self.assertIs(last_input[1], marker)
        outputs = [
            item
            for item in last_input
            if isinstance(item, dict) and item.get("type") == "function_call_output"
        ]
        self.assertEqual(
            [item["call_id"] for item in outputs],
            ["price-1", "math-1", "math-2"],
        )
        self.assertEqual(json.loads(outputs[-1]["output"]), {"result": 250})

    def test_tool_error_is_returned_as_observation(self):
        client = Mock()
        client.responses.create.side_effect = [
            response(
                [tool_call("get_product_price", {"product": "未知の商品"}, "bad")]
            ),
            response([tool_call("get_product_price", {"product": "ペン"}, "good")]),
            response(text="ペンは120円です。"),
        ]

        result = ReActRunner(client, "gpt-6-luna").run(
            [
                {"role": "user", "content": "商品の価格は？"},
            ]
        )

        second_input = client.responses.create.call_args_list[1].kwargs["input"]
        self.assertIn("error", json.loads(second_input[-1]["output"]))
        self.assertEqual(result.content, "ペンは120円です。")

    def test_max_steps_stops_without_an_extra_request(self):
        client = Mock()
        client.responses.create.return_value = response(
            [
                tool_call("get_product_price", {"product": "ノート"}, "price-1"),
            ]
        )
        with self.assertRaises(ReActLimitError):
            ReActRunner(client, "gpt-6-luna", max_steps=1).run(
                [
                    {"role": "user", "content": "価格は？"},
                ]
            )
        self.assertEqual(client.responses.create.call_count, 1)

    def test_incomplete_empty_and_refused_responses_fail(self):
        refusal = SimpleNamespace(
            type="message",
            content=[SimpleNamespace(type="refusal", refusal="拒否の例")],
        )
        for invalid in [
            response(status="incomplete"),
            response(text="  "),
            response(output=[refusal]),
        ]:
            with self.subTest(response=invalid):
                client = Mock()
                client.responses.create.return_value = invalid
                with self.assertRaises(ReActError):
                    ReActRunner(client, "gpt-6-luna").run([])

    def test_step_limit_is_validated_without_http(self):
        for limit in [0, 9, True]:
            with self.subTest(limit=limit):
                with self.assertRaises(ReActConfigurationError):
                    ReActRunner(Mock(), "gpt-6-luna", max_steps=limit)

    def test_tools_reject_invalid_inputs(self):
        cases = [
            ("unknown", "{}"),
            ("calculate", "not-json"),
            ("calculate", "[]"),
            ("calculate", '{"operation":"divide","left":1,"right":0}'),
            ("calculate", '{"operation":"add","left":true,"right":1}'),
            ("calculate", '{"operation":"add","left":1e999,"right":1}'),
            ("calculate", '{"operation":[],"left":1,"right":1}'),
            ("get_product_price", '{"product":"ノート","extra":1}'),
        ]
        for name, arguments in cases:
            with self.subTest(name=name, arguments=arguments):
                self.assertIn("error", execute_tool(name, arguments))

    def test_agent_prompt_and_limits_are_sent_without_mutating_input(self):
        client = Mock()
        completed = response(text="回答")
        completed.usage = None
        client.responses.create.return_value = completed
        messages = [{"role": "user", "content": "質問"}]

        result = ReActRunner(
            client,
            "gpt-6-luna",
            system_prompt="講義用の指示",
        ).run(messages)

        sent = client.responses.create.call_args.kwargs
        self.assertEqual(sent["model"], "gpt-6-luna")
        self.assertEqual(sent["instructions"], INSTRUCTIONS + "\n講義用の指示")
        self.assertFalse(sent["parallel_tool_calls"])
        self.assertEqual(sent["max_output_tokens"], 512)
        self.assertEqual(result.usage["total_tokens"], 0)
        self.assertEqual(messages, [{"role": "user", "content": "質問"}])
