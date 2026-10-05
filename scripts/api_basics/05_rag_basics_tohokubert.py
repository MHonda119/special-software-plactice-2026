"""文書検索と回答生成を組み合わせる RAG の最小例。"""

import argparse
from functools import partial
from math import sqrt
from pathlib import Path

from common import EMBEDDING_MODEL, TEXT_MODEL, new_client


# [注1] RAG（Retrieval-Augmented Generation、検索拡張生成）は、関連文書の検索と
# その文書を使う回答生成を組み合わせます。文書を入力に添える仕組みで、
# ここではモデルの追加学習は行いません。
docs = [
    {"id": 1, "text": "当社の有給休暇は入社初年度は20日付与です。半休制度もあります。"},
    {"id": 2, "text": "あなたの残り有給日数は5日です。"},
    {"id": 3, "text": "開発環境はDockerとVSCode Dev Containersを推奨しています。テンプレートは社内Gitにあります。"},
    {"id": 4, "text": "東京オフィスの来客受付は6階です。セキュリティゲートを通過するにはQRコードが必要です。"},
]


# [注2] 文書と質問は同じモデル・設定で埋め込み、同じ意味の座標空間で比較します。
# ベクトルの次元数が同じでも、異なるモデルで作った値を混ぜて比較することはできません。
def embed_openai(texts, model=EMBEDDING_MODEL, batch=128, client=None):
    """OpenAI Embeddings は複数の文字列をまとめて受け取れる。"""
    if batch < 1:
        raise ValueError("batch は 1 以上にしてください。")
    if client is None:
        client = new_client()
    vectors = []
    # [注3] batch 件ずつまとめて送ると、文書ごとのAPI呼び出しを減らせます。
    # 戻り値を各バッチ内のindex順に並べ、元の文書とベクトルの対応を保ちます。
    for start in range(0, len(texts), batch):
        response = client.embeddings.create(
            model=model, input=texts[start:start + batch]
        )
        vectors.extend(item.embedding for item in sorted(response.data, key=lambda d: d.index))
    return vectors


# [注4] 追加ライブラリとモデルは、TohokuBERTを選択したときだけ読み込みます。
# OpenAIの埋め込みを使う場合は、このローカルモデルの準備やダウンロードは不要です。
def make_tohokubert_embedder():
    """任意演習用。選択したときだけ追加ライブラリとモデルを読み込む。"""
    try:
        import fugashi  # noqa: F401: tokenizer が内部で利用する
        import ipadic  # noqa: F401: このモデルの日本語辞書
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:
        requirements = Path(__file__).resolve().with_name("requirements-tohokubert.txt")
        raise SystemExit(
            "TohokuBERT の追加依存が必要です。\n"
            f'python -m pip install -r "{requirements}"'
        ) from exc

    # 初回は Hugging Face から tokenizer とモデルをダウンロードする。
    model_name = "cl-tohoku/bert-base-japanese"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    # [注5] eval() はDropoutなどを推論用の動作に切り替えます。
    # 下のno_grad() は学習用の勾配を記録せず、メモリ消費を抑えます。役割は別です。
    model.eval()

    def embed(texts, batch=8):
        vectors = []
        for start in range(0, len(texts), batch):
            # [注6] tokenizer は文章をトークンIDに変換し、padding は埋め草で長さをそろえます。
            # truncation は長すぎる入力の切り詰めです。切り詰められた部分は埋め込みに反映されません。
            encoded = tokenizer(
                texts[start:start + batch], padding=True, truncation=True,
                return_tensors="pt",
            )
            with torch.no_grad():
                hidden = model(**encoded).last_hidden_state  # [文書数, トークン数, 次元数]
                # [注7] attention_mask でpaddingを除き、トークンのベクトルを平均します
                # （平均プーリング）。このBERTは文書検索専用の学習をしたモデルではないため、
                # この方法で必要な文書が見つかるか、実際の質問で確かめる必要があります。
                mask = encoded["attention_mask"].unsqueeze(-1)
                mean = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
                vectors.extend(mean.cpu().tolist())
        return vectors

    return embed


# [注8] コサイン類似度はベクトルの向きの近さを-1〜1で表す指標で、確率ではありません。
# 値が高くても、その文書が質問への答えを含むことや、内容の正しさは保証されません。
def cosine_similarity(left, right):
    if len(left) != len(right):
        raise ValueError("文書と質問の埋め込み次元が異なります。同じモデルを使ってください。")
    denominator = sqrt(sum(value * value for value in left)) * sqrt(
        sum(value * value for value in right)
    )
    if denominator == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / denominator


# [注9] top_k は類似度の上位から残す文書数です。増やすと参照情報も入力の利用量も増えます。
# この例は類似度の最低条件を設けていないため、関連する文書がなくても上位の文書を返します。
def retrieve(query, documents, doc_vectors, embedder, top_k=2):
    query_vector = embedder([query])[0]
    scored_docs = [
        (doc, cosine_similarity(query_vector, vector))
        for doc, vector in zip(documents, doc_vectors)
    ]
    return sorted(scored_docs, key=lambda item: item[1], reverse=True)[:top_k]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--embedding-backend", choices=("openai", "tohokubert"), default="openai",
        help="埋め込みの生成方法（既定: openai）。回答生成にはどちらも OpenAI API を使用。",
    )
    parser.add_argument("--question", default="わたしの残り有給日数は何日でしょうか？")
    args = parser.parse_args()

    client = new_client()
    if args.embedding_backend == "tohokubert":
        embedder = make_tohokubert_embedder()
    else:
        # [注10] partial はclientとmodelの引数を固定します。できたembedderにはtextsだけ渡せばよく、
        # 文書と質問の両方に同じモデルとクライアントを使えます。
        embedder = partial(embed_openai, client=client, model=EMBEDDING_MODEL)

    # 文書と質問に同じ embedder を渡すことで、モデルの混在を防ぐ。
    doc_vectors = embedder([doc["text"] for doc in docs])
    hits = retrieve(args.question, docs, doc_vectors, embedder)
    print("Query:", args.question)
    for rank, (doc, score) in enumerate(hits, 1):
        print(f"[{rank}] score={score:.3f} id={doc['id']} text={doc['text']}")

    # [注11] 検索結果を参考文書（コンテキスト）として渡し、そこを根拠に答えるよう指示します。
    # 根拠がないときは「分からない」と答えるよう指示しますが、検索漏れや誤回答は起こり得ます。
    # 正しく答えられない場合は、生成文だけでなく検索された文書も確認します。
    context = "\n".join(f"- {doc['text']}" for doc, _ in hits)
    response = client.responses.create(
        model=TEXT_MODEL,
        reasoning={"effort": "none"},
        max_output_tokens=300,
        instructions=(
            "与えられた参考文書を使って、質問に日本語で簡潔に答えてください。"
            "参考文書に答えがない場合は、分からないと答えてください。"
        ),
        input=f"参考文書:\n{context}\n\n質問: {args.question}",
    )
    print("=== QUESTION & ANSWER ===")
    print("Question:", args.question)
    print("Answer:", response.output_text)


if __name__ == "__main__":
    main()
