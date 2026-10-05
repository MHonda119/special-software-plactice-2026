"""Responses API で構造化出力と温度による違いを試す。"""

import argparse
import json

from common import TEXT_MODEL, new_client


# [注1] JSON Schema は出力の項目と型を決める設計図です。required は必須項目、
# enum は選べる値、additionalProperties=False は定義外の項目を禁止する指定です。
PLACE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "category": {"type": "string", "enum": ["museum", "shopping", "food", "other"]},
        "nearest_station": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["title", "category", "nearest_station", "reason"],
    "additionalProperties": False,
}

MESSAGES = [
    {
        "role": "system",
        "content": (
            "日本語で短く回答してください。JSONにはtitle、category"
            "（museum, shopping, food, otherのいずれか）、nearest_station、reasonを"
            "含めてください。reasonは1文にしてください。"
        ),
    },
    {
        "role": "user",
        "content": "東京で、比較的落ち着いて過ごせそうな屋内スポットを1つ提案してください。",
    },
]


def completed_text(response):
    """拒否や未完了を、正常な回答として扱わない。"""
    # [注2] 構造化出力でも回答の拒否や、上限到達による未完了は起こります。
    # 部分的なJSONや空の回答を読み進めないよう、解析する前に状態と内容を確かめます。
    if response.status != "completed":
        reason = getattr(response.incomplete_details, "reason", None) or response.status
        raise RuntimeError(f"応答が完了していません: {reason}")
    for item in response.output:
        if item.type == "message":
            for content in item.content:
                if content.type == "refusal":
                    raise RuntimeError(f"モデルが回答を拒否しました: {content.refusal}")
    text = response.output_text.strip()
    if not text:
        raise RuntimeError("応答にテキストがありません。")
    return text


def parse_recommendation(text):
    """JSONをPythonの辞書にし、利用する項目を確認する。"""
    # [注3] json.loads はJSON文字列をPythonの値に変換します。
    # 変換後も辞書の項目・型・選択肢を確認すると、後の処理で安心して参照できます。
    data = json.loads(text)
    if not isinstance(data, dict) or set(data) != set(PLACE_SCHEMA["required"]):
        raise ValueError("構造化出力の項目がスキーマと一致しません。")
    if not all(isinstance(value, str) for value in data.values()):
        raise ValueError("構造化出力の各項目は文字列である必要があります。")
    if data["category"] not in PLACE_SCHEMA["properties"]["category"]["enum"]:
        raise ValueError("構造化出力のcategoryが指定した選択肢に含まれていません。")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    # [注4] 試行ごとにAPIを呼びます。既定では構造化出力1回と温度比較9回の計10回です。
    # --repeats 1 なら計4回になり、動作確認時の待ち時間と利用量を減らせます。
    parser.add_argument("--repeats", type=int, default=3, help="各温度での試行回数（既定: 3）")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats は1以上にしてください。")

    client = new_client()
    print(f"Model: {TEXT_MODEL}")

    # [注5] Responses API では text.format にスキーマを指定します。strict=True は
    # 完了した通常の回答を指定形式にそろえますが、施設情報の正確さや最新性は保証しません。
    response = client.responses.create(
        model=TEXT_MODEL,
        input=MESSAGES,
        reasoning={"effort": "none"},
        # [注6] トークンは文章を分割した単位で、日本語の文字数とは一致しません。
        # max_output_tokens は出力の上限です。小さすぎると文やJSONが途中で切れます。
        max_output_tokens=512,
        text={
            "format": {
                "type": "json_schema",
                "name": "place_reco",
                "schema": PLACE_SCHEMA,
                "strict": True,
            }
        },
    )
    recommendation = parse_recommendation(completed_text(response))
    print("Structured Response:")
    # [注7] json.dumps はPythonの値をJSON文字列に戻します。ensure_ascii=False で
    # 日本語をそのまま表示し、indent=2 で読みやすく字下げします。
    print(json.dumps(recommendation, ensure_ascii=False, indent=2))

    # [注8] 温度を上げると語の選び方が多様になる傾向があります。正確さを高める設定ではありません。
    # 同じ入力で繰り返して違いを観察します。温度0でも毎回の完全な一致は保証されません。
    # [注9] GPT-6 Luna で温度を指定するには reasoning.effort="none" が必要です。
    # この比較ではスキーマを指定していないため、注5と異なりAPIによるJSON形式の保証はありません。
    for temperature in (0, 1, 2):
        for index in range(args.repeats):
            response = client.responses.create(
                model=TEXT_MODEL,
                input=MESSAGES,
                reasoning={"effort": "none"},
                temperature=temperature,
                max_output_tokens=512,
            )
            print(f"Temperature {temperature}, trial {index + 1}:")
            print(completed_text(response))


if __name__ == "__main__":
    main()
