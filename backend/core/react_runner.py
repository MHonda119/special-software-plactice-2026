import json
from dataclasses import dataclass

from .react_tools import TOOLS, execute_tool


INSTRUCTIONS = (
    "あなたは演習用の商品について答えるアシスタントです。"
    "質問に必要なツールを選び、その結果から次の行動を決めてください。"
    "商品価格は必ず get_product_price で確認し、"
    "計算は必ず calculate を使ってください。"
    "ツールエラーが出たら引数を修正するか、回答できない理由を説明してください。"
    "必要な情報がそろったら、結果に基づいて日本語で簡潔に回答してください。"
)


class ReActError(RuntimeError):
    pass


class ReActLimitError(ReActError):
    pass


class ReActConfigurationError(ValueError):
    pass


@dataclass
class ReActResult:
    content: str
    usage: dict


class ReActRunner:
    def __init__(self, client, model, max_steps=8, system_prompt=""):
        if type(max_steps) is not int or not 1 <= max_steps <= 8:
            raise ReActConfigurationError("max_steps は 1-8 にしてください。")
        self.client = client
        self.model = model
        self.max_steps = max_steps
        self.instructions = INSTRUCTIONS + (
            "\n" + system_prompt if system_prompt else ""
        )

    def run(self, messages):
        history = list(messages)
        usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        for step in range(self.max_steps):
            response = self.client.responses.create(
                model=self.model,
                instructions=self.instructions,
                input=list(history),
                tools=TOOLS,
                tool_choice="auto",
                parallel_tool_calls=False,
                reasoning={"effort": "none"},
                max_output_tokens=512,
            )
            if response.status != "completed":
                raise ReActError("モデルの応答が完了しませんでした。")

            for item in response.output:
                if item.type == "message":
                    for content in item.content:
                        if content.type == "refusal":
                            raise ReActError("モデルが回答を拒否しました。")

            for key in usage:
                value = getattr(response.usage, key, None)
                if type(value) is int:
                    usage[key] += value

            history.extend(response.output)
            calls = [
                item
                for item in response.output
                if item.type == "function_call"
            ]
            if not calls:
                answer = response.output_text.strip()
                if not answer:
                    raise ReActError("最終回答が空でした。")
                return ReActResult(content=answer, usage=usage)

            for call in calls:
                result = execute_tool(call.name, call.arguments)
                history.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(
                            result, ensure_ascii=False, allow_nan=False
                        ),
                    }
                )

        raise ReActLimitError("最大ステップ数に達しました。")
