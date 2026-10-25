# セッションAPI

会話セッションのCRUD、メッセージ履歴取得、LLMへのチャット送信を提供する。共通の認証・エラー形式は [README.md](README.md) を参照。

## エンドポイント

| メソッド | パス | 概要 | 成功 |
| --- | --- | --- | --- |
| GET | `/api/sessions/` | 一覧取得 | 200 |
| POST | `/api/sessions/` | 作成 | 201 |
| GET | `/api/sessions/{uuid}/` | 詳細取得 | 200 |
| PUT | `/api/sessions/{uuid}/` | 更新 | 200 |
| PATCH | `/api/sessions/{uuid}/` | 部分更新 | 200 |
| DELETE | `/api/sessions/{uuid}/` | 物理削除 | 204 |
| GET | `/api/sessions/{uuid}/messages/` | メッセージ履歴取得 | 200 |
| POST | `/api/sessions/{uuid}/chat/` | チャット送信 | 200 |

`{uuid}` は整数IDではなく、セッションのUUID主キー。

## セッションのフィールド

CRUDでは以下の3フィールドだけを公開する。「必須」はPOST/PUTでの入力要否で、PATCHでは省略できる。

| フィールド | 型 | 必須 | 既定値・制約 |
| --- | --- | --- | --- |
| uuid | string (UUID) | 入力不可 | 自動生成。読み取り専用 |
| llm | integer | 必須 | 存在するLLMのID。`null` 不可。非アクティブなLLMも指定可能 |
| title | string | 任意 | `New Session`。最大200文字。空文字・`null` 不可 |

モデル内部の `agent`、`metadata`、`is_active`、`created_at`、`updated_at` はこのCRUDの入出力には含めない。`is_active` やエージェントとの紐付けをこのAPIで設定することはできない。

## 作成

`POST /api/sessions/`

```json
{
  "llm": 1,
  "title": "APIについての相談"
}
```

レスポンス: `201 Created`。

```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "llm": 1,
  "title": "APIについての相談"
}
```

- `title` を省略すると `New Session`。
- 作成時にはLLM呼び出しやメッセージ追加を行わない。
- エージェントとの紐付けが必要な場合は [エージェント実行API](agents.md) でセッションを生成する。

## 一覧・詳細取得

`GET /api/sessions/` は `200 OK` で配列を返す。リクエストボディは不要。対象がなければ `[]`。

```json
[
  {
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "llm": 1,
    "title": "APIについての相談"
  }
]
```

`GET /api/sessions/{uuid}/` は配列内と同じ形の単一オブジェクトを返す。

- `is_active=true` のセッションだけが対象。詳細取得、更新、削除、履歴取得も同じ制限を受ける。
- エージェント経由で生成したアクティブなセッションも一覧に含まれるが、`agent` は返さない。
- ページング、検索、LLM・エージェント等による絞り込み、並べ替えパラメータはない。一覧の順序も指定されていない。
- 通常のCRUD・履歴取得で対象が存在しないか非アクティブなら `404`。`chat` の例外処理は後述。

## 更新・削除

`PUT /api/sessions/{uuid}/` は `llm` が必須。`PATCH /api/sessions/{uuid}/` は指定項目だけを更新する。

```json
{
  "title": "API仕様レビュー"
}
```

成功時は `200 OK` で、`uuid`、`llm`、`title` を持つ更新後オブジェクトを返す。

- `llm` の変更も可能。既存の履歴は削除されない。
- `DELETE /api/sessions/{uuid}/` は物理削除。`204 No Content`、ボディなし。
- セッション削除時は、紐付くすべてのメッセージも `CASCADE` で削除する。
- 通常のセッションCRUDに論理削除APIはなく、`DELETE` で `is_active=false` にする実装ではない。

## メッセージ履歴取得

`GET /api/sessions/{uuid}/messages/`

ボディ・専用クエリパラメータは不要。成功時は `200 OK`。

```json
[
  {
    "id": 1,
    "role": "user",
    "content": "こんにちは",
    "created_at": "2026-10-25T10:00:00Z"
  },
  {
    "id": 2,
    "role": "assistant",
    "content": "こんにちは。",
    "created_at": "2026-10-25T10:00:01Z"
  }
]
```

| フィールド | 型 | 説明 |
| --- | --- | --- |
| id | integer | メッセージID |
| role | string | `system` / `user` / `assistant` / `tool` |
| content | string | メッセージ本文 |
| created_at | string (datetime) | 作成日時 |

- `created_at` 昇順。ページングなしで全件を返す。空の履歴は `[]`。
- 同一作成日時のメッセージ間の順序について、追加のソートキーはない。
- `usage`、`metadata`、`name`、`session` はレスポンスに含めない。
- エージェントのsystem promptやRAGのコンテキストも、保存されていれば `system` メッセージとして返す。
- メッセージ単体の作成・編集・削除APIはない。

## チャット送信

`POST /api/sessions/{uuid}/chat/`

### リクエスト

| フィールド | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| message | string | 必須 | 前後の空白を除去して保存・送信。未指定・空文字・空白だけなら `400` |
| options | object / null | 任意 | LLM生成パラメータ。省略・`null` は追加指定なし |

```json
{
  "message": "REST APIとは何ですか？",
  "options": {
    "temperature": 0.3
  }
}
```

### レスポンス

成功時は `200 OK`。

```json
{
  "session_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "assistant_message": {
    "id": 4,
    "role": "assistant",
    "content": "REST APIはリソースをHTTPで操作するためのAPIです。"
  },
  "usage": {
    "eval_count": 42
  }
}
```

| フィールド | 型 | 説明 |
| --- | --- | --- |
| session_uuid | string (UUID) | 使用したセッション |
| assistant_message | object | 新たに保存した回答。`id`、固定値 `assistant` の `role`、`content` |
| usage | object | プロバイダ別の利用量 |

### 処理・オプション

1. アクティブなセッションを検索する。
2. `user` メッセージを保存する。
3. セッションの全メッセージを作成日時順で取得し、`role` と `content` をLLMに渡す。
4. 応答を `assistant` メッセージとして保存し、利用量とともに返す。

ユーザー入力の保存から回答の保存まではDBトランザクション内で実行する。LLM呼び出し等で例外が起きると、この呼び出しで作成したメッセージはロールバックされる。

LLMクライアントは `llm.extra` を既定値とし、リクエストの `options` で上書きする。

| provider | 生成パラメータの扱い | usage |
| --- | --- | --- |
| OLLAMA / CUSTOM | マージ結果を外部APIの `options` に渡す | `eval_count` |
| OPENAI | `temperature`, `top_p`, `n`, `stream`, `stop`, `max_tokens`, `presence_penalty`, `frequency_penalty`, `logit_bias`, `user` のみ転送 | `prompt_tokens`, `completion_tokens`, `total_tokens` |
| GEMINI | `temperature`, `top_p`, `top_k`, `max_output_tokens` を `generationConfig` に設定 | `prompt_tokens`, `completion_tokens`, `total_tokens` |

利用量の各値は外部応答に値がなければ `null` となる場合がある。`stream=true` によるストリーミング利用は非対応。

このエンドポイントは `ChatInSessionUsecase` を直接実行する。セッションにエージェントが紐付いていても、エージェントの `config` のマージ、system promptの新規挿入、RAG検索は行わない。それらが必要な場合は `/api/agents/{id}/execute/` を使う。

### エラー・制約

| ステータス | 条件・レスポンス |
| --- | --- |
| 400 | 未指定・空のmessage: `{"detail":"message is required"}` |
| 500になり得る | 対象セッションの不存在・非アクティブ・UUID不正。通常CRUDと違い、直接のORM検索の例外を `404` 等に変換しない |
| 500になり得る | messageが `null` / 非文字列、optionsが非オブジェクトなど。専用Serializerによる型検証はない |
| 500になり得る | 外部LLMの接続・HTTP・タイムアウトエラー、APIキー不足、その他の未処理例外 |

`message` を直接 `.strip()` するため、型不正を整形済みの `400` で返す保証はない。外部LLMの失敗を `502` / `504` に変換する処理もない。

## 実装参照

- [ChatSessionViewSet](../../../backend/core/views.py)
- [ChatSessionCreateSerializer・MessageSerializer](../../../backend/core/serializers.py)
- [ChatSession・Message](../../../backend/core/models.py)
- [ChatInSessionUsecase](../../../backend/core/usecases.py)
- [LLMクライアント・usage](../../../backend/core/llm_clients.py)
