from common import new_client
client = new_client()

texts = [
    "今日は雨です。",
    "明日は晴れでしょう。",
    "機械学習で重要なのはデータ品質です。"
]

emb = client.embeddings.create(
    model="text-embedding-3-small",
    input=texts
)
# ベクトル次元や一部値を確認
print("dim:", len(emb.data[0].embedding), "vectors:", len(emb.data))
print("usage:", emb.usage)  # input_tokens / total_tokens など
