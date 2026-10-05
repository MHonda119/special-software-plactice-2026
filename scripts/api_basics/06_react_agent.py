"""ReAct の「判断 → ツール実行 → 結果の観測」を繰り返す小さなエージェント。"""

import argparse
import json
from math import isfinite
import operator

from common import TEXT_MODEL, new_client


# [注1] ReAct は Reason（次の行動を判断）→ Act（ツール実行）→ Observe（結果の観測）を繰り返す考え方です。
# この例は Action と Observation を表示し、モデル内部の思考過程は表示しません。
# 6-1 ローカルで実行する簡易ツール。価格は演習用の架空データ。
# [注2] この辞書を演習の商品データとして使います。価格は固定値なので、計算結果を手元でも確認できます。
PRODUCT_PRICES = {"ノート": 250, "ペン": 120, "消しゴム": 80}
OPERATIONS = {
    "add": operator.add,
    "subtract": operator.sub,
    "multiply": operator.mul,
    "divide": operator.truediv,
}


def get_product_price(product):
    if not isinstance(product, str) or product not in PRODUCT_PRICES:
        raise ValueError("商品が見つかりません。登録商品: " + "、".join(PRODUCT_PRICES))
    return {"product": product, "price_yen": PRODUCT_PRICES[product]}


def calculate(operation, a, b):
    """式の eval は使わず、指定された四則演算だけを実行する。"""
    # [注3] モデルから受け取った文字列を eval で実行せず、登録済みの演算関数を選びます。
    # 数値の型と有限性も確認し、不正な値や計算結果をツールのエラーとして扱います。
    if operation not in OPERATIONS:
        raise ValueError("operation は add/subtract/multiply/divide のいずれかです。")
    if any(type(value) not in (int, float) or not isfinite(value) for value in (a, b)):
        raise ValueError("a と b には有限の数値を指定してください。")
    result = OPERATIONS[operation](a, b)
    if not isfinite(result):
        raise ValueError("計算結果が数値の範囲を超えました。")
    return {"result": result}


# 6-2 ツールの名前・用途・引数を JSON Schema でモデルに伝える。
# [注4] スキーマはモデルに渡す「呼び出し方の説明」です。関数の処理内容は含みません。
# strict と required、additionalProperties により、引数の項目と型を指定した形にそろえます。
TOOLS = [
    {
        "type": "function",
        "name": "get_product_price",
        "description": "演習用の商品価格を円単位で取得する。登録商品はノート、ペン、消しゴム。",
        "parameters": {
            "type": "object",
            "properties": {"product": {"type": "string", "description": "商品名"}},
            "required": ["product"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "calculate",
        "description": "2つの数値で四則演算を行う。subtract は a-b、divide は a/b。",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": list(OPERATIONS)},
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["operation", "a", "b"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]
# [注5] こちらはツール名と実際の Python 関数を対応させる実行用の辞書です。
# モデルは名前と引数を返して実行を要求し、このプログラムが登録された関数を呼び出します。
TOOL_FUNCTIONS = {"get_product_price": get_product_price, "calculate": calculate}

INSTRUCTIONS = (
    "あなたは演習用の商品について答えるアシスタントです。"
    "質問に答えるために必要なツールを選び、その結果を見て次の行動を決めてください。"
    "商品価格は必ず get_product_price で確認し、計算は必ず calculate を使ってください。"
    "ツールにエラーが出たら引数を修正するか、回答できない理由を説明してください。"
    "必要な情報がそろったら、結果に基づいて日本語で簡潔に回答してください。"
)


def execute_tool(name, arguments_json):
    """実行できる関数を限定し、ツールのエラーも観測結果としてモデルに返す。"""
    if name not in TOOL_FUNCTIONS:
        return {"error": f"未登録のツールです: {name}"}
    try:
        # [注6] 引数は JSON 文字列で届くため、json.loads で辞書へ変換します。
        # **arguments は辞書のキーを引数名として展開します。たとえば {"a": 250} は a=250 に相当します。
        arguments = json.loads(arguments_json)
        if not isinstance(arguments, dict):
            raise ValueError("ツールの引数は JSON オブジェクトにしてください。")
        return TOOL_FUNCTIONS[name](**arguments)
    except (ValueError, TypeError, ArithmeticError) as exc:
        # [注7] 引数の誤りやゼロ除算も、モデルが次の行動を判断するための観測結果にします。
        # エラーの内容を受け取ったモデルは、引数の修正や回答の終了を選べます。
        return {"error": str(exc)}


class ReActAgent:
    # [注8] API クライアントを外から渡す設計です。通信部分を差し替えて、API を使わずに動作確認もできます。
    def __init__(self, client, model=TEXT_MODEL, max_steps=8):
        if max_steps < 1:
            raise ValueError("max_steps は1以上にしてください。")
        self.client = client
        self.model = model
        self.max_steps = max_steps

    def run(self, question):
        # [注9] run ごとに新しい履歴を作ります。1回の実行中は、質問・モデルの出力・ツール結果を蓄積します。
        history = [{"role": "user", "content": question}]

        # 6-3 モデルが次の行動を選び、ツール結果を観測して再び判断する。
        # [注10] 1ステップはモデルへの問い合わせ1回です。最終回答を作る問い合わせも上限に含みます。
        # たとえば価格取得・乗算・減算を別々に要求し、最後に回答する場合は4ステップ必要です。
        for step in range(1, self.max_steps + 1):
            print(f"\n[Step {step}]")
            response = self.client.responses.create(
                model=self.model,
                instructions=INSTRUCTIONS,
                input=history,
                tools=TOOLS,
                tool_choice="auto",
                # [注11] 同じ応答で複数のツールを同時に要求しない設定です。
                # この例では、価格を取得した結果を見てから計算を選ぶ、順番のある流れを学びます。
                parallel_tool_calls=False,
                reasoning={"effort": "none"},
                max_output_tokens=512,
            )
            if response.status != "completed":
                raise RuntimeError(f"モデルの応答が完了しませんでした: {response.status}")
            for item in response.output:
                if item.type == "message":
                    for content in item.content:
                        if content.type == "refusal":
                            raise RuntimeError(f"モデルが回答を拒否しました: {content.refusal}")

            # ツール呼び出しを含むモデルの出力全体を、次のリクエストに引き継ぐ。
            # [注12] output はツール呼び出しなどを含む項目の一覧、output_text は回答テキストを取り出す補助機能です。
            # 履歴には output 全体を追加し、推論項目などが含まれる場合も省略せず引き継ぎます。
            history.extend(response.output)
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                answer = response.output_text.strip()
                if not answer:
                    raise RuntimeError("最終回答が空でした。")
                return answer

            for call in calls:
                print(f"[Action] {call.name}({call.arguments})")
                result = execute_tool(call.name, call.arguments)
                observation = json.dumps(result, ensure_ascii=False, allow_nan=False)
                print(f"[Observation] {observation}")
                # [注13] call_id は「どの呼び出しへの結果か」を示す識別子です。同じ値を返して対応付けます。
                # output には、関数の戻り値を JSON 文字列に変換した観測結果を入れます。
                history.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": observation,
                })

        raise RuntimeError(f"最大ステップ数 {self.max_steps} に達したため終了しました。")


def main():
    # [注14] --question と --max-steps で、ソースを書き換えずに質問と上限を変更できます。
    # 引数を省略すると、下に指定された default の値を使います。
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--question", default="ノートを3冊買って1000円を支払うと、お釣りはいくらですか？",
    )
    parser.add_argument("--max-steps", type=int, default=8, help="モデルへの問い合わせ上限（既定: 8）")
    args = parser.parse_args()
    if args.max_steps < 1 or not args.question.strip():
        parser.error("--max-steps は1以上、--question は空でない文字列にしてください。")

    print("Question:", args.question)
    try:
        with new_client() as client:
            agent = ReActAgent(client, max_steps=args.max_steps)
            answer = agent.run(args.question)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print("\n[Final Answer]", answer)


# [注15] このファイルを直接実行したときだけ main を呼びます。import 時は関数やクラスを読み込めます。
if __name__ == "__main__":
    main()
