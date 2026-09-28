# Datasource API 仕様
最終更新: 2025-11-16

## 1. 概要
Datasource API は Retrieval Augmented Generation (RAG) 向けに参照可能な **テキストチャンク集合** を管理するための最小機能 (MVP) を提供します。投入されたテキストとタイトルをそのまま **ベクトル埋め込み (embedding)** に変換し **ChromaDB** に保持します。MVP では以下を「意図的に」除外します:
- 自動チャンク分割 (Chunking)
- 正規化 / クリーニング / 重複排除
- メタデータ高度管理 (タグ, ソースURL 等)

将来 Agent の Usecase (例: `RAG_CHAT`) で Datasource を指定し、検索で取得したチャンクをコンテキストとして LLM 応答に統合します。

## 2. 背景 / 目的
現在 RAG 利用を想定した文書管理層が存在せず、任意テキストを保持する標準化されたストアが無い。シンプルな MVP を早期提供し、以下を素早く検証する:
1. 埋め込みモデル / 保存実装 (Chroma) の整合性
2. 類似検索の速度・品質
3. 将来の拡張インターフェース (chunking / metadata / versioning) のフレーム

## 3. 用語定義
| 用語 | 説明 |
|------|------|
| Datasource | 文書チャンク集合の論理コンテナ。検索単位 |
| Chunk | 1 つのテキスト断片 (MVP: 依頼時に既に分割済みとみなす) |
| Embedding | テキストを固定長ベクトルへ写像した結果。類似度計算に利用 |
| Collection | ChromaDB 内の格納単位。`datasource_<id>` 形式で作成 |
| Top-K | 類似検索時に返す上位件数 |

## 4. MVP スコープ
| 項目 | 対応 |
|------|------|
| Datasource CRUD | 作成 / 一覧 / 単一取得 / 削除のみ (更新は名称変更程度) |
| Chunk 登録 | POST `/datasources/{id}/chunks/` (指定 ID のコンテナに 1 チャンク追加) |
| 検索 | 未実装 (将来 `/datasource/{id}/search/`) |
| バルク登録 | 未実装 (将来 `/bulk/`) |
| チャンク更新 / 削除 | 未実装 (将来個別管理) |
| メタデータ | `title` のみ、内部的に `metadata.title` として保存 |
| マルチ Embed モデル | 未対応 (Datasource 個別指定廃止。将来 retrieval オプションで一時切替) |

## 5. ドメインモデル
### 5.1 Datasource (DB)
| フィールド | 型 | 必須 | 説明 |
|------------|----|------|------|
| id | integer | - | PK |
| name | string(<=100) | 必須 | 表示/識別名 |
| description | text | 任意 | 説明文 |
| llm | FK(LLM) | 必須 | 既存 LLM モデル参照 (埋め込み生成に利用する設定。常に `llm.model`) |
| is_active | bool | 任意 (default true) | 非アクティブで検索対象外 |
| created_at | datetime | - | 生成時間 |
| updated_at | datetime | - | 更新時間 |

### 5.2 Chunk (Chroma 側 保存形)
MVP では Django DB に永続化せず **ChromaDB のみ** に保持。
| フィールド (概念) | 説明 |
|-------------------|------|
| id (uuid) | Chroma に保存する識別子 (生成: `uuid4()`) |
| datasource_id | コレクション名から暗黙的に判別 (`datasource_<id>`) |
| text | ユーザ送信した生チャンク文字列 |
| title | ユーザ送信タイトル (metadata.title) |
| embedding | 埋め込みベクトル (内部利用 / API レスポンス非公開) |
| created_at | metadata へ `ts` として付与可能 |

## 6. 埋め込み / 保存フロー (チャンク登録)
1. クライアントが `POST /api/datasources/{id}/chunks/` に `title`, `chunk_text` を送信
2. API が Datasource 存在 & active を検証
3. 埋め込みモデル取得: `datasource.llm.model` (固定。実験的オーバーライドは retrieval_overrides.embed_model)
4. 埋め込み生成 (Ollama / 専用エンドポイント: 例 `POST /api/embeddings` 仮)
5. Chroma コレクション取得 (なければ作成)
6. `collection.add(ids=[uuid], metadatas=[{title}], documents=[chunk_text], embeddings=[vector])`
7. 応答として `chunk_id`, `title`, `text_length` 等を返却

シーケンス (概念):
```
Client -> API: POST /api/datasources/12/ {title, chunk_text}
API -> DB: Get Datasource[id=12]
API -> Embedding Model: embed(chunk_text)
Embedding Model -> API: vector[dim]
API -> Chroma: collection.add(...)
Chroma -> API: ack
API -> Client: {chunk_id, datasource_id, title}
```

## 7. エンドポイント定義 (MVP)
ベースパス案: `/api/datasources/`
| メソッド | パス | 説明 |
|----------|------|------|
| GET | /api/datasources/ | Datasource 一覧 |
| POST | /api/datasources/ | Datasource 作成 |
| GET | /api/datasources/{id}/ | 単一取得 |
| PATCH | /api/datasources/{id}/ | 部分更新 (name/description) |
| DELETE | /api/datasources/{id}/ | 削除 (論理 or 物理) |
| POST | /api/datasources/{id}/chunks/ | 指定 Datasource へ 1 チャンク追加 |
| GET | /api/datasources/{id}/chunks/ | チャンク一覧取得 (Chroma コレクション内) |
| DELETE | /api/datasources/{id}/chunks/{chunk_id}/ | 単一チャンク削除 |

> 設計注: チャンクは独立リソースとして `/api/datasources/{id}/chunks/` で登録。将来 `DELETE /api/datasources/{id}/chunks/{chunk_id}/` などへ自然拡張可能。

## 8. リクエスト / レスポンス例
### 8.1 Datasource 作成 (POST /api/datasources/)
リクエスト:
```json
{
  "name": "Docs A",
  "description": "社内ナレッジベース MVP"
}
```
レスポンス (201):
```json
{
  "id": 12,
  "name": "Docs A",
  "description": "社内ナレッジベース MVP",
  "is_active": true
}
```

### 8.2 チャンク登録 (POST /api/datasources/{id}/chunks/)
リクエスト:
```json
{
  "title": "RAG 概要",
  "chunk_text": "RAG は Retrieval Augmented Generation の略で ..."
}
```
レスポンス (201):
```json
{
  "datasource_id": 12,
  "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "RAG 概要",
  "text_length": 42
}
```

### 8.3 バリデーションエラー
### 8.4 チャンク一覧取得 (GET /api/datasources/{id}/chunks/)
クエリパラメータ:
- `limit` (int, 任意, default=20, 1-100): 取得件数
- `offset` (int, 任意, default=0, 0以上): 先頭からのスキップ件数

レスポンス (200):
```json
{
  "datasource_id": 12,
  "count": 2,
  "limit": 20,
  "offset": 0,
  "chunks": [
    {
      "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "RAG 概要",
      "text_length": 42
    },
    {
      "chunk_id": "111e8400-e29b-41d4-a716-446655440000",
      "title": "設計メモ",
      "text_length": 120
    }
  ]
}
```

存在しない / inactive Datasource → 404

### 8.5 チャンク削除 (DELETE /api/datasources/{id}/chunks/{chunk_id}/)
レスポンス (204): 空ボディ。

エラー:
| ステータス | 例 | 原因 |
|------------|----|------|
| 404 | {"detail":"Datasource not found"} | Datasource 不存在 / inactive |
| 404 | {"detail":"Chunk not found"} | chunk_id 未存在 |
| 500 | - | Vector store 内部例外 |

```json
{"detail": "title and chunk_text are required"}
```
ステータス: 400

## 9. シリアライザ / バリデーション案
- `DatasourceSerializer` (GET): `id,name,description,is_active`
- `DatasourceCreateUpdateSerializer`: 必須 name, llm (埋め込み用)。llm は既存 LLM モデル ID。
- `DatasourceChunkCreateSerializer` (POST /{id}/chunks/): 入力 `title(str, required)`, `chunk_text(str, required, max_length=10000)`
- レスポンスは内部構造露出を避けシンプル: `datasource_id, chunk_id, title, text_length`

## 10. 埋め込み実装詳細
| 項目 | 内容 |
|------|------|
| モデル取得 | `datasource.llm.model` (既存 LLM モデルの設定を利用: provider/base_url/model/extra) |
| クライアント | Ollama embeddings (`POST /api/embeddings` 仮) / 直接 HTTP 呼び出し |
| ベクトル次元 | モデルに依存 (例: 768 / 1024) – レスポンス非公開 |
| 失敗時リトライ | なし (将来: 3 回指数バックオフ) |
| タイムアウト | 30s (仮) |

将来: OpenAI / Gemini Embeddings (LLM provider 経由), ベクトル次元検証, キャッシュ化 (同一テキスト判定ハッシュ)。

## 11. エラー定義
| ステータス | 例 | 原因 |
|------------|----|------|
| 400 | {"detail":"title and chunk_text are required"} | 必須フィールド欠如 |
| 404 | - | Datasource 不存在 / inactive |
| 422 | {"detail":"embedding generation failed"} | 埋め込み失敗 (モデル未応答) |
| 500 | - | Chroma 追加内部例外 |
| 404 | {"detail":"Chunk not found"} | 削除 / 取得対象 chunk 不存在 |

## 12 削除時の Chroma カスケード動作
`DELETE /api/datasources/{id}/` 実行時の挙動方針:
| 削除種別 | 説明 | Chroma コレクション (`datasource_<id>`) | 失敗時リカバリ |
|-----------|------|-------------------------------------------|----------------|
| 物理削除 | レコード完全削除 | 即座に drop (存在しなければ無視) | コレクション drop 失敗→ 500 / 将来は再試行 & tombstone |
| 論理削除 (is_active=false) | 復活可能運用 | 保持 (検索対象から除外) | - |

実装概要 (物理削除例):
1. DB トランザクション開始
2. Datasource レコード削除
3. トランザクション完了後に Chroma コレクション削除 (二段階) で DB ロールバック影響を避ける
4. コレクションが既に無い場合は成功扱い (冪等性確保)

パフォーマンス注意: 大量チャンク削除は内部で O(件数) のファイル/インデックス縮小を伴う可能性。将来は非同期ジョブ化 (削除要求→ 状態 `PENDING_DROP` → バックグラウンド処理) を検討。


## 13. Agent 連携
Agent UsecaseType `RAG_CHAT` 実装時、`config.datasource_ids` を指定すると:
1. ユーザ入力を埋め込み
2. 各 Datasource コレクションで top_k 検索
3. スコア閾値でフィルタ
4. コンテキストテンプレートへ挿入
5. LLM 呼び出し

レスポンス拡張例:
```json
{
  "message": {"role":"assistant","content":"..."},
  "citations": [
    {"datasource_id":12,"chunk_id":"...","score":0.82,"title":"RAG 概要"}
  ]
}
```

## 14. テスト項目 (MVP)
- Datasource 作成: name 必須 / llm 必須
- チャンク登録: 正常系 (201) / 空 title / 空 chunk_text / 長さ超過
- 埋め込み失敗 (モックで例外) → 422
- 非アクティブ Datasource への登録拒否
- 複数チャンク連続登録後 Chroma 内件数一致
- 物理削除: レコード消失 + コレクション drop 呼び出し確認
- 論理削除: is_active=false 設定で登録/検索拒否 (検索実装後)

## 15. CURL サンプル
```bash
# Datasource 作成
curl -X POST http://localhost:8000/api/datasources/ \
  -H 'Content-Type: application/json' \
  -d '{"name":"Docs A"}'

# チャンク登録 (POST /api/datasources/{id}/chunks/)
curl -X POST http://localhost:8000/api/datasources/12/chunks/ \
  -H 'Content-Type: application/json' \
  -d '{"title":"RAG 概要","chunk_text":"RAG は ..."}'
```

---
MVPのため以下は今回考えない。参考までに

## セキュリティ / 運用
| 項目 | 現状 | 将来案 |
|------|------|--------|
| 認証 | 無し | Token / RBAC (Agent との関連付け) |
| アクセス制御 | 無し | Datasource 所有者 / グループ権限 |
| レート制限 | 無し | チャンク登録 API Throttle |
| データ削除 | 物理/論理選択未定 | 物理 + Embedding GC / Vector tombstone |
| PII マスク | 未対応 | プレ処理で除去 / 暗号化検討 |

## パフォーマンス / サイズ制約 (暫定)
| 項目 | 暫定値 | 理由 |
|------|--------|------|
| chunk_text 長さ | <= 10,000 chars | メモリ極端膨張回避 |
| 1 Datasource チャンク数 | <= 50,000 (ソフト上限) | Chroma コレクション負荷予測 |
| 登録 QPS | 低 (<<10) | MVP 検証フェーズ |

監視指標案: 追加失敗率 / 埋め込み平均レイテンシ / コレクションサイズ。

## 非機能要件 (MVP 想定)
| 項目 | 目標 |
|------|------|
| レイテンシ (登録) | < 2s (埋め込み+保存) |
| 可用性 | ベストエフォート (開発環境) |
| 障害復旧 | Chroma 永続ボリューム破損時再構築 (再投入) |
| ログ | INFO: 開始/成功/失敗; DEBUG: 埋め込みサイズ |

## リスクと注意
- コレクション名衝突: 命名規則固定で回避 (`datasource_<id>`)
- 大量長文投入: chunk_text 上限で制御、将来は自動分割
- PII 流入: MVP では未検査。運用ルールで事前マスク
- モデル変更時の再埋め込み: 再生成バッチ設計必要

## 拡張ロードマップ
| フェーズ | 内容 |
|---------|------|
| v1 | MVP: 単一登録 API / Datasource CRUD |
| v2 | 検索 API (similarity top_k), chunk 個別削除/更新 |
| v3 | 自動チャンク分割 (長文→分割) + 正規化 (改行整形 / 言語判定) |
| v4 | 高度メタデータ (source_url, tags, author, version) |
| v5 | 埋め込みモデル複数対応 / 再埋め込みジョブ |
| v6 | キャッシュ / 重複検出 / 近似最近傍 (HNSW) パラメータ調整 |


## 今後の設計検討メモ
- Chunk を RDB にも保存し監査/論理削除可能にする
- Embedding の遅延生成 (ジョブキュー) 導入で応答待ち時間の短縮、非同期化
- RAG 検索アルゴリズム: cosine vs inner product 選択 & スコア正規化、手法はいろいろ
