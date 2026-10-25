# LLM API

外部LLMの接続先、モデル、APIキー、生成パラメータの既定値を管理する。共通の認証・エラー形式は [README.md](README.md) を参照。

## エンドポイント

| メソッド | パス | 概要 | 成功 |
| --- | --- | --- | --- |
| GET | `/api/llms/` | 一覧取得 | 200 |
| POST | `/api/llms/` | 作成 | 201 |
| GET | `/api/llms/{id}/` | 詳細取得 | 200 |
| PUT | `/api/llms/{id}/` | 更新 | 200 |
| PATCH | `/api/llms/{id}/` | 部分更新 | 200 |
| DELETE | `/api/llms/{id}/` | 物理削除 | 204 |

`{id}` はLLMの整数主キー。通常の一覧・詳細取得には、`is_active=false` のLLMも含まれる。ページング、検索、並べ替え、`is_active` 等のクエリフィルターは未実装で、一覧順序は指定されていない。

## フィールド

「必須」はPOSTおよびPUTでの入力要否。PATCHでは省略できる。`null` の明示的な許可は表に示す。

| フィールド | 型 | 必須 | 既定値・制約 |
| --- | --- | --- | --- |
| id | integer | 入力不可 | 自動採番。読み取り専用 |
| name | string | 必須 | 最大100文字。空文字不可。名前の一意制約なし |
| provider | string | 任意 | `OLLAMA`。`OLLAMA` / `OPENAI` / `GEMINI` / `CUSTOM` |
| base_url | string / null | 任意 | `null`。空文字可。最大255文字。URL形式の検証なし |
| model | string | 必須 | 最大100文字。空文字不可。モデルの存在・利用可否は登録時に検証しない |
| api_key | string / null | 条件付き | `null`。空文字可。OPENAI/GEMINIの検証は後述 |
| extra | JSON | 任意 | `{}`。実行時の生成パラメータの既定値。オブジェクトを指定する |
| is_active | boolean | 任意 | `true` |

`extra` はJSONFieldのため、入力時にオブジェクト専用の型検証や各キーの検証は行わない。しかし実行コードは辞書としてマージするため、配列・文字列などを設定するとチャット等で失敗する可能性がある。`extra` に `null` は指定できない。

### APIキーの検証・返却

- 作成時、`provider=OPENAI` または `GEMINI` では、空でない `api_key` が必要。未指定・`null`・空文字は `400`。
- 更新時の検証は「送信値または既存値」を参照する。既存キーがあれば省略できるが、既存キーがある状態で `null` / 空文字を送ると、既存値で検証を通過した後に送信値が保存される場合がある。以降の実行ではキー不足で失敗する。
- GETの一覧・詳細レスポンスには `api_key` フィールド自体を含めない。
- POST/PUT/PATCHのレスポンスには `api_key` が含まれ、実際の値をそのまま返す。マスク処理・write-only設定はない。ログや共有資料に記録しない。

## 作成

`POST /api/llms/`

```json
{
  "name": "Local Chat",
  "provider": "OLLAMA",
  "base_url": "http://ollama:11434",
  "model": "llama3:8b",
  "extra": {"temperature": 0.7},
  "is_active": true
}
```

レスポンス: `201 Created`。

```json
{
  "id": 1,
  "name": "Local Chat",
  "provider": "OLLAMA",
  "base_url": "http://ollama:11434",
  "model": "llama3:8b",
  "api_key": null,
  "extra": {"temperature": 0.7},
  "is_active": true
}
```

## 一覧・詳細取得

`GET /api/llms/` は `200 OK` で配列を返す。対象がなければ `[]`。リクエストボディは不要。

```json
[
  {
    "id": 1,
    "name": "Local Chat",
    "provider": "OLLAMA",
    "base_url": "http://ollama:11434",
    "model": "llama3:8b",
    "extra": {"temperature": 0.7},
    "is_active": true
  }
]
```

`GET /api/llms/1/` は配列内と同じ形の単一オブジェクトを返す。対象がなければ `404`。

## 更新

`PUT /api/llms/{id}/` は `name`、`model` が必須。`PATCH /api/llms/{id}/` は変更する項目だけを指定する。

```json
{
  "extra": {"temperature": 0.3},
  "is_active": false
}
```

成功時はどちらも `200 OK` で、作成時と同じフィールド構成の更新後オブジェクトを返す。`extra` はオブジェクト全体が置換される。`is_active=false` にしてもこのCRUDから取得・再更新でき、チャットの実行可否を強制的に制限するフラグとしては使われていない。

## 削除

`DELETE /api/llms/{id}/` はボディ不要。成功時は `204 No Content`、レスポンスボディなし。

`ChatSession.llm`、`Agent.llm`、`Datasource.llm` はすべて `PROTECT`。いずれかに参照されているLLMは削除できない。非アクティブな参照先も削除制約の対象になる。参照を解消してから削除する。

`ProtectedError` をHTTPエラーへ明示変換する処理はないため、参照中の削除は未処理例外による `500` となり得る。`409 Conflict` を返す仕様ではない。

## 実行時のプロバイダ解決

| provider | チャットの接続先 | base_url省略・空値時の既定 |
| --- | --- | --- |
| OLLAMA | `{base_url}/api/chat` | `OLLAMA_BASE_URL`、未設定なら `http://ollama:11434` |
| OPENAI | `{base_url}/chat/completions` | `OPENAI_BASE_URL`、未設定なら `https://api.openai.com/v1` |
| GEMINI | `{base_url}/v1beta/models/{model}:generateContent` | `GEMINI_BASE_URL`、未設定なら `https://generativelanguage.googleapis.com` |
| CUSTOM | 現実装ではOLLAMAクライアントにフォールバック | OLLAMAと同じ |

登録・更新時に疎通確認は行わない。外部HTTP呼び出しのチャットタイムアウトは `LLM_REQUEST_TIMEOUT`、既定60秒。埋め込み対応は [データソースAPI](datasources.md) を参照。

## エラー

| ステータス | 条件 |
| --- | --- |
| 400 | 必須項目不足、最大長超過、不正なprovider、OPENAI/GEMINIのキー不足など |
| 404 | 指定IDが存在しない |
| 500 | 参照中のLLM削除などの未処理例外 |

APIキー不足の例:

```json
{
  "api_key": ["This field is required for the selected provider."]
}
```

## 実装参照

- [LLMViewSet](../../../backend/core/views.py)
- [LLMSerializer・LLMCreateUpdateSerializer](../../../backend/core/serializers.py)
- [LLMと外部キー制約](../../../backend/core/models.py)
- [プロバイダ選択・LLMクライアント](../../../backend/core/llm_clients.py)
