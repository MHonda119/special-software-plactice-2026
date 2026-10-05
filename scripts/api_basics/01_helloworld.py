"""Responses API で短い挨拶を生成し、トークン使用量を確認する。"""

# [注1] common.py は各演習で共有する設定。TEXT_MODEL はモデル名、
# new_client は環境変数や .env の API キーを使って通信の準備をする関数。
from common import TEXT_MODEL, new_client


def main():
    # [注2] with を使うと、ブロックを抜ける際にクライアントの接続が閉じられる。
    # 実際にモデルへリクエストを送るのは responses.create の行。
    with new_client() as client:
        resp = client.responses.create(
            model=TEXT_MODEL,
            # [注3] input はモデルに渡す指示（プロンプト）。この英文を変えると、
            # 翻訳・要約など別の課題も試せる。生成結果は実行ごとに変わる場合がある。
            input="Say hello in one short sentence.",
            # [注4] reasoning は推論の設定。ここでは GPT-6 Luna が対応する none を使う。
            # 別のモデルを選ぶ場合、そのモデルが同じ設定値に対応するかを確認する。
            reasoning={"effort": "none"},
            # [注5] 上限の単位は文字数ではなく、モデルが文章を処理する単位「トークン」。
            # 1文字と1トークンは一致せず、上限まで必ず生成するわけでもない。
            max_output_tokens=128,
        )
    # [注6] output_text は応答から生成テキストを取り出すための便利な属性。
    # usage には入力・出力・合計のトークン数が入り、利用量を把握する目安になる。
    print(resp.output_text)
    print(resp.usage)


# [注7] このファイルを python で直接実行した場合だけ main を呼ぶ。
# 他の Python ファイルから import しただけでは、API 呼び出しは始まらない。
if __name__ == "__main__":
    main()
