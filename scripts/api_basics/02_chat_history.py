"""Chat Completions API に会話履歴を渡して、文脈を引き継ぐ。"""

from common import TEXT_MODEL, new_client


def main():
    user_q = "雨でも楽しめて、混雑が少ない穴場は？"
    # [注1] messages は古い発言から順に並べる。role は発言の役割を表し、
    # system は応答方針、user は利用者の質問、assistant はモデル側の発言を意味する。
    # この例の過去の assistant 発言は、演習用にあらかじめ用意した文字列。
    messages = [
        {"role": "system", "content": "You are a friendly assistant that answers concisely."},
        {"role": "user", "content": "今日は東京で何をすると良い？屋内で。"},
        {"role": "assistant", "content": "美術館や科学館、ショッピングモールなどはいかがでしょう。"},
        {"role": "user", "content": user_q},
    ]

    # [注2] この API の使い方では、引き継ぎたい履歴を毎回 messages に含める。
    # ここに「東京」「屋内」の条件があるため、最後の質問で省略しても参照できる。
    # 履歴も入力トークンに数えられるので、長い会話ほど1回の入力が増える。
    with new_client() as client:
        resp = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=messages,
            # [注3] 01 の Responses API と同じ目的でも、引数や応答の形は異なる。
            # ここでは reasoning_effort と max_completion_tokens という名前を使う。
            reasoning_effort="none",
            max_completion_tokens=512,
        )

    # [注4] choices は返された回答候補の配列。この例では先頭の候補を取り出す。
    # API 呼び出しが成功しても、拒否や出力上限による中断があり得るため、
    # refusal と finish_reason を確認してから回答として利用する。
    message = resp.choices[0].message
    if message.refusal:
        raise SystemExit(f"応答が拒否されました: {message.refusal}")
    if resp.choices[0].finish_reason != "stop":
        raise SystemExit(
            f"応答が完了しませんでした: {resp.choices[0].finish_reason}。"
            "max_completion_tokens などの設定を確認してください。"
        )
    reply = message.content
    # [注5] 回答を履歴へ追加すると、次の質問を追記して会話を続けられる。
    # append は手元のリストを変更するだけ。この例では次の API 呼び出しは行わない。
    messages.append({"role": "assistant", "content": reply})

    print("User:", user_q)
    print("Assistant:", reply)
    # [注6] Chat Completions の usage は prompt_tokens（入力）、
    # completion_tokens（出力）、total_tokens（合計）などで利用量を表す。
    print(resp.usage)


# [注7] 直接実行したときだけ会話例を動かし、import 時の API 呼び出しを防ぐ。
if __name__ == "__main__":
    main()
