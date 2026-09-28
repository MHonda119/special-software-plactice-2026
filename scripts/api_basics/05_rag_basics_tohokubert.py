from common import new_client
import torch, numpy as np
from transformers import AutoTokenizer, AutoModel
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm

## pip install transformers protobuf fugashi unidic_lite

# 5-1 事前コーパス（例：独自のFAQやナレッジ）を用意
docs = [
    {"id":1, "text":"当社の有給休暇は入社初年度は20日付与です。半休制度もあります。"},
    {"id":2, "text":"あなたの残り有給日数は5日です。"},
    {"id":3, "text":"開発環境はDockerとVSCode Dev Containersを推奨しています。テンプレートは社内Gitにあります。"},
    {"id":4, "text":"東京オフィスの来客受付は6階です。セキュリティゲートを通過するにはQRコードが必要です。"},
]

# 5-2 TohokuBERT で埋め込み
tok = AutoTokenizer.from_pretrained("cl-tohoku/bert-base-japanese")
mdl = AutoModel.from_pretrained("cl-tohoku/bert-base-japanese")
mdl.eval()

def embed(texts, batch=8):
    vecs = []
    for i in tqdm(range(0, len(texts), batch)):
        batch_texts = texts[i:i+batch]
        with torch.no_grad():
            enc = tok(batch_texts, padding=True, truncation=True, return_tensors="pt")
            out = mdl(**enc).last_hidden_state  # [B, T, H]
            # mean pooling（パディング無視用にattention_maskで重み付け平均するのがより厳密）
            mask = enc["attention_mask"].unsqueeze(-1)  # [B,T,1]
            summed = (out * mask).sum(dim=1)
            counts = mask.sum(dim=1).clamp(min=1)
            mean = (summed / counts).cpu().numpy()
            vecs.append(mean)
    return np.vstack(vecs)

def embed_openai(texts, model: str = "text-embedding-3-small", batch: int = 128, client=None, show_progress: bool = True):
    client = new_client()
    vecs = []
    rng = range(0, len(texts), batch)
    iterator = tqdm(rng) if show_progress else rng
    for i in iterator:
        batch_texts = texts[i:i+batch]
        # OpenAI Embeddings はバッチ配列を受け取り、各要素に対応する data を返す
        resp = client.embeddings.create(model=model, input=batch_texts)
        # 念のため index で並び替え、入力順を保証
        sorted_data = sorted(resp.data, key=lambda d: getattr(d, "index", 0))
        batch_vecs = np.array([d.embedding for d in sorted_data], dtype=np.float32)
        vecs.append(batch_vecs)

    return np.vstack(vecs)

# 5-3 質問に対して最近傍（コサイン類似）を検索
# OpenAI Embeddings を使う場合は embed_openai() を使う
def retrieve(query, top_k=2):
    # qv = embed([query])[0].reshape(1, -1)  # [1,H]
    qv = embed_openai([query])[0].reshape(1, -1)  # [1,H]

    sims = cosine_similarity(qv, doc_vecs)[0]  # [N]
    idx = np.argsort(-sims)[:top_k]
    return [(docs[i], float(sims[i])) for i in idx]



#　ここから下は実行例

## ドキュメントをベクトル化
doc_texts = [d["text"] for d in docs]
# doc_vecs = embed(doc_texts)  # [N, H]
doc_vecs = embed_openai(doc_texts, model="text-embedding-3-small")  # [N, H]


q = "わたしの残り有給日数は何日でしょうか？"
hits = retrieve(q, top_k=2)
print("Query:", q)
for rank,(d,score) in enumerate(hits,1):
    print(f"[{rank}] score={score:.3f} id={d['id']} text={d['text']}")

# 検索結果をコンテキストとして Chat Completions API に渡す
client = new_client()
resp=client.chat.completions.create(
    model="gpt-5-chat-latest",
    messages=[
        {"role": "system", "content": "You are a helpful assistant. Use the provided context to answer the user's question."},
        {"role": "user", "content": "Context:\n" + "\n".join([f"- {d['text']}" for d, _ in hits])},
        {"role": "user", "content": q}
    ]
)
print("=== QUESTION & ANSWER ===")
print("Question:", q)
print("Answer:", resp.choices[0].message.content)