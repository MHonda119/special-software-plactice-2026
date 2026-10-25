# データソースAPI

RAG用のデータソースと、Chromaに保存するテキストチャンクを管理する。共通の認証・エラー形式は [README.md](README.md) を参照。

## エンドポイント

| メソッド | パス | 概要 | 成功 |
| --- | --- | --- | --- |
| GET | `/api/datasources/` | 一覧取得 | 200 |
| POST | `/api/datasources/` | 作成 | 201 |
| GET | `/api/datasources/{id}/` | 詳細取得 | 200 |
| PUT | `/api/datasources/{id}/` | 更新 | 200 |
| PATCH | `/api/datasources/{id}/` | 部分更新 | 200 |
| DELETE | `/api/datasources/{id}/` | データソースとコレクションを削除 | 204 |
| GET | `/api/datasources/{id}/chunks/` | チャンク一覧 | 200 |
| POST | `/api/datasources/{id}/chunks/` | チャンク登録・埋め込み生成 | 201 |
| DELETE | `/api/datasources/{id}/chunks/{chunk_id}/` | チャンク削除 | 204 |

`{id}` はデータソースの整数主キー。チャンクIDは登録時にUUID文字列を生成するが、削除URLはUUID形式を検証せず、`/` と `.` を含まない文字列を受け付ける。

## データソースのフィールド

「必須」はPOST/PUTでの入力要否で、PATCHでは省略できる。

| フィールド | 型 | 必須 | 既定値・制約 |
| --- | --- | --- | --- |
| id | integer | 入力不可 | 自動採番。読み取り専用 |
| name | string | 必須 | 最大100文字。空文字・空白だけ・`null` 不可。一意制約なし |
| description | string / null | 任意 | `null`。空文字可 |
| llm | integer | 必須 | 存在するLLMのID。埋め込みに `llm.model` を使う。`null` 不可 |
| is_active | boolean | 任意 | `true` |

通常のCRUDは非アクティブなデータソースも対象。一覧はページングなしの配列で、検索・絞り込み・並べ替えパラメータはない。順序も指定されていない。`created_at` / `updated_at` やチャンクはCRUDレスポンスに含めない。

## 作成

`POST /api/datasources/`

```json
{
  "name": "APIマニュアル",
  "description": "RAG検索用の資料",
  "llm": 2
}
```

レスポンス: `201 Created`。

```json
{
  "id": 1,
  "name": "APIマニュアル",
  "description": "RAG検索用の資料",
  "llm": 2,
  "is_active": true
}
```

作成時に外部LLMへ接続したり、Chromaコレクションを生成したりはしない。非アクティブなLLMも参照可能。LLMの埋め込み対応状況やAPIキーは、チャンク登録時の処理で問題になる。

## 一覧・詳細取得

`GET /api/datasources/` は `200 OK` で配列を返す。リクエストボディ不要。対象がなければ `[]`。

```json
[
  {
    "id": 1,
    "name": "APIマニュアル",
    "description": "RAG検索用の資料",
    "llm": 2,
    "is_active": true
  }
]
```

`GET /api/datasources/{id}/` は配列内と同じ形の単一オブジェクトを返す。

## 更新・削除

`PUT /api/datasources/{id}/` は `name` と `llm` が必須。`PATCH /api/datasources/{id}/` は指定項目だけを更新する。

```json
{
  "description": "更新した資料",
  "is_active": false
}
```

成功時は `200 OK` で更新後の全公開フィールドを返す。

- 非アクティブにしても通常CRUDは利用でき、PATCHで `is_active=true` に戻せる。
- 非アクティブにすると、このAPIのチャンク登録・一覧・削除は `404`。
- `llm` を変更しても既存チャンクの再埋め込みは行わない。検索時のベクトル空間・次元の互換性は利用側で維持する必要がある。

`DELETE /api/datasources/{id}/` はボディ不要。成功時は `204 No Content`、ボディなし。

1. DBのデータソースを物理削除する。
2. Chromaの `datasource_{id}` コレクション削除を試みる。

コレクション削除自体の例外はログ出力して無視するため、削除漏れでも `204` となる場合がある。一方、Chromaクライアントの初期化例外は捕捉されず、DB削除後に `500` となる可能性がある。DBとChromaをまたぐ原子的な削除は保証しない。

エージェントの `config.datasource_ids` はJSONであり、ここから削除したIDの自動除去は行わない。

## チャンク登録

`POST /api/datasources/{id}/chunks/`

### リクエスト

| フィールド | 型 | 必須 | 制約 |
| --- | --- | --- | --- |
| title | string | 必須 | 最大200文字。空文字・空白だけ・`null` 不可 |
| chunk_text | string | 必須 | 最大10,000文字。空文字・空白だけ・`null` 不可 |

```json
{
  "title": "RAG概要",
  "chunk_text": "RAG combines search and generation."
}
```

前後の空白は除去して保存する。1回のリクエストで1チャンクを追加する。自動分割・ファイルアップロード・一括登録は行わない。

### レスポンス

成功時は `201 Created`。

```json
{
  "datasource_id": 1,
  "chunk_id": "660e8400-e29b-41d4-a716-446655440000",
  "title": "RAG概要",
  "text_length": 35
}
```

| フィールド | 型 | 説明 |
| --- | --- | --- |
| datasource_id | integer | 対象データソースのID |
| chunk_id | string (UUID) | 新規生成したチャンクID |
| title | string | 保存したタイトル |
| text_length | integer | 空白除去後の本文のPython `len`。バイト数・トークン数ではない |

### 保存・埋め込み

- 本文を関連LLMで埋め込み、Chromaに `documents=[chunk_text]`、`metadatas=[{"title":title}]`、生成ベクトルを保存する。チャンク本体はDjangoモデルとしては保存しない。
- コレクション名は `datasource_{id}`。未作成なら作成する。
- 同一本文でも毎回新規UUIDで `add` する。重複排除やupsertではない。
- 永続化先は `CHROMA_PERSIST_DIR`、未設定なら `/data/chroma`。

| LLM provider | 外部呼び出し | モデル・認証 |
| --- | --- | --- |
| OLLAMA | `{base_url}/api/embeddings` に `{"model":...,"prompt":...}` | `datasource.llm.model`。APIキー不要 |
| OPENAI | `{base_url}/embeddings` に `{"model":...,"input":...}` | `datasource.llm.model`。Bearer APIキー必須 |
| GEMINI / CUSTOM | 非対応 | `EmbeddingError` |

base_urlの既定は [LLM API](llms.md) と同じ。埋め込みHTTP呼び出しのタイムアウトは固定30秒で、`LLM_REQUEST_TIMEOUT` とは異なる。チャンク登録ボディで埋め込みモデルを上書きするフィールドはない。

## チャンク一覧

`GET /api/datasources/{id}/chunks/?limit=20&offset=0`

| クエリ | 型 | 既定 | 制約 |
| --- | --- | --- | --- |
| limit | integer | 20 | 1以上100以下 |
| offset | integer | 0 | 0以上 |

ボディ不要。成功時は `200 OK`。

```json
{
  "datasource_id": 1,
  "count": 1,
  "limit": 20,
  "offset": 0,
  "chunks": [
    {
      "chunk_id": "660e8400-e29b-41d4-a716-446655440000",
      "title": "RAG概要",
      "text_length": 35
    }
  ]
}
```

- `count` は今回返した `chunks` の件数。コレクション全体の総件数ではない。
- タイトルがない場合は `title=null`。本文・ベクトル・任意のmetadataは返さない。
- コレクションが取得できない場合は `count=0`、`chunks=[]`。取得時の例外を広く空扱いするため、必ずしも未作成だけを意味しない。
- 明示的なソートをしておらず、返却順はChromaに依存する。
- 範囲外のoffsetなどで取得対象がない場合も、空の配列を返す。

## チャンク削除

`DELETE /api/datasources/{id}/chunks/{chunk_id}/`

ボディ不要。存在確認後に削除し、成功時は `204 No Content`、ボディなし。存在しない場合は `404` のため、繰り返し削除しても常に `204` になるわけではない。

- コレクション未取得・チャンク未検出に加え、削除前のチャンク取得に失敗した場合も `Chunk not found` となり得る。
- チャンク単体の詳細取得・更新APIはない。本文を変更する場合は削除後に別チャンクとして登録する。

## エラー

| 対象 | ステータス | 条件・detail |
| --- | --- | --- |
| CRUD/登録 | 400 | 必須不足、最大長超過、空文字、不正な関連LLMなど。項目別エラー |
| 全詳細操作 | 404 | データソースのIDが存在しない |
| 全チャンク操作 | 404 | 非アクティブ: `Datasource inactive` |
| チャンク登録 | 422 | 捕捉対象の埋め込み生成失敗: `embedding generation failed` |
| チャンク一覧 | 400 | limit/offsetを整数変換できない: `invalid limit/offset` |
| チャンク一覧 | 400 | limit範囲外: `limit out of range` |
| チャンク一覧 | 400 | offsetが負数: `offset out of range` |
| チャンク一覧 | 500 | ストア処理等の例外: `failed to list chunks` |
| チャンク削除 | 404 | 未検出: `Chunk not found` |
| チャンク削除 | 500 | 捕捉対象のストア例外: `internal error` |

埋め込み生成失敗のレスポンス例:

```json
{
  "detail": "embedding generation failed"
}
```

`422` には、OPENAIのAPIキー不足、非対応provider、埋め込みHTTPリクエスト失敗、ベクトルを取得できない場合が含まれる。チャンク登録が捕捉するのは `EmbeddingError` のみで、Chromaの追加処理やそれ以外の例外は整形されず `500` となり得る。

## 実装参照

- [DatasourceViewSet・chunks・delete_chunk_action](../../../backend/core/views.py)
- [データソース・チャンクのSerializer](../../../backend/core/serializers.py)
- [Datasource](../../../backend/core/models.py)
- [埋め込み生成・Chroma操作](../../../backend/core/datasource_store.py)
