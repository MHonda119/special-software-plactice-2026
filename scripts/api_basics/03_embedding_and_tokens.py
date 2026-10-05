"""複数の文章をベクトル化し、次元数と入力トークン使用量を確認する。"""

from common import EMBEDDING_MODEL, new_client


def main():
    # [注1] Embedding（埋め込み）は、文章を数値の配列「ベクトル」に変換する処理。
    # 文章同士の関連性を比較するために使い、チャットのような回答文は生成しない。
    texts = [
        "今日は雨です。",
        "明日は晴れでしょう。",
        "機械学習で重要なのはデータ品質です。",
    ]
    # [注2] 文字列のリストを input に渡すと、複数の文章を1回のリクエストで送れる。
    # 応答の data には各文章の結果が入り、各要素の index が元の入力位置を示す。
    with new_client() as client:
        emb = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)

    print("model:", EMBEDDING_MODEL)
    # [注3] 「次元数」は1つのベクトルに含まれる数値の個数、「vectors」は文章の個数。
    # 既定では small が1536次元、large が3072次元で、この例はどちらも3ベクトルになる。
    print("dim:", len(emb.data[0].embedding), "vectors:", len(emb.data))
    # [注4] 数千個の数値をすべて表示すると読みにくいため、先頭5個だけ確認する。
    # 個々の値を特定の単語の意味に対応付けるのではなく、ベクトル全体を比較に使う。
    print("first 5 values:", emb.data[0].embedding[:5])
    # [注5] Embedding の課金に関係するのは入力トークン数で、次元数とは別の量。
    # この応答には文章生成の completion_tokens はなく、prompt_tokens などが入る。
    print("usage:", emb.usage)  # prompt_tokens / total_tokens（生成トークンはない）


# [注6] この例のベクトルはメモリ上だけにある。05 の RAG 演習では、同じように
# 作った文書ベクトルと質問ベクトルを比較して、関連する文書を検索する。
if __name__ == "__main__":
    main()
