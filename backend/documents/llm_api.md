# LLM API ドキュメント

## 概要
LLM エンドポイントはチャット利用可能な LLM 設定（接続先 URL, モデル名, 追加パラメータ）を CRUD 操作するための管理 API です。現在の実装では **Ollama** クライアントのみが実行時に利用されます（`provider` フィールドは将来拡張用）。

ベースパス: `/api/llms/`

## モデル項目
| フィールド | 型 | 必須 | 説明 |
|-----------|----|------|------|
| id | integer | - | 自動採番 ID |
| name | string(<=100) | 必須 | 論理名（UI 表示用）|
| provider | enum | 任意(デフォルト OLLAMA) | `OLLAMA` / `OPENAI` / `GEMINI` / `CUSTOM` |
| base_url | string | 任意 | LLM API のベース URL。未指定時 `OLLAMA_BASE_URL` env (デフォルト `http://ollama:11434`) |
| model | string(<=100) | 必須 | モデル名 (例: `llama3:8b`) |
| api_key | text | 任意 | 将来 OpenAI 等で利用予定。リスト取得では非表示（create/update のみ）|
| extra | object(JSON) | 任意 | 追加パラメータ（Ollama options の初期値など）|
| is_active | boolean | 任意 (default true) | 利用可否フラグ |

## シリアライザ差異
- GET (list/retrieve): `LLMSerializer` （`api_key` を返さない）
- POST / PUT / PATCH: `LLMCreateUpdateSerializer` （`api_key` を送受信可能）

## Provider 別実行仕様 (拡張後)

### 1. OLLAMA
- デフォルト `base_url`: `http://ollama:11434` (env `OLLAMA_BASE_URL` 上書き可)
- エンドポイント: `POST {base_url}/api/chat`
- 送信 JSON: `{model, messages, options, stream:false}`
- usage: `{"eval_count": <int>}`

### 2. OPENAI
- デフォルト `base_url`: `https://api.openai.com/v1` (env `OPENAI_BASE_URL` 上書き可)
- 必須: `api_key`
- エンドポイント: `POST {base_url}/chat/completions`
- ヘッダ: `Authorization: Bearer <api_key>`
- 送信 JSON 例:
  ```json
  {
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "Hello"}
    ],
    "temperature": 0.7
  }
  ```
- 応答抽出: `choices[0].message.content`
- usage 正規化: `prompt_tokens`, `completion_tokens`, `total_tokens`

### 3. GEMINI
- デフォルト `base_url`: `https://generativelanguage.googleapis.com` (env `GEMINI_BASE_URL` 上書き可)
- 必須: `api_key`
- エンドポイント: `POST {base_url}/v1beta/models/{model}:generateContent?key=<api_key>`
- 送信 JSON (簡易):
  ```json
  {
    "contents": [
      {"role": "user", "parts": [{"text": "こんにちは"}]}
    ],
    "generationConfig": {"temperature": 0.7}
  }
  ```
- 応答抽出: `candidates[0].content.parts[].text` を連結
- usage 正規化: `prompt_tokens`, `completion_tokens`, `total_tokens` （元: `usageMetadata.promptTokenCount`, `candidatesTokenCount`, `totalTokenCount`）

### 4. 共通オプションマージ
`LLM.extra` (DB 保存されたデフォルト) と API 呼び出し時の `options` ボディをマージし、後者優先。Gemini の場合は `generationConfig` に代表キーのみ（temperature / top_p / top_k / max_output_tokens）。

### 5. バリデーション
- provider が `OPENAI` / `GEMINI` の場合 `api_key` 必須 (サーバ側で検証)
- `OLLAMA` は不要

### 6. エラー時挙動
- HTTP ステータス 4xx/5xx は `requests` の `raise_for_status()` により例外化→上位で 500 応答（現状簡易実装）
- 改善余地: プロバイダ別レスポンスマッピング / タイムアウト明示 / 再試行ポリシ

## エンドポイント一覧
| メソッド | パス | 説明 |
|----------|------|------|
| GET | /api/llms/ | LLM 一覧取得 |
| POST | /api/llms/ | LLM 作成 |
| GET | /api/llms/{id}/ | 単一取得 |
| PUT | /api/llms/{id}/ | 全更新 |
| PATCH | /api/llms/{id}/ | 一部更新 |
| DELETE | /api/llms/{id}/ | 削除 |

## リクエスト例
### 作成 (POST /api/llms/)
```json
{
  "name": "Local Llama3",
  "provider": "OLLAMA",
  "base_url": "http://ollama:11434",
  "model": "llama3:8b",
  "api_key": null,
  "extra": {"temperature": 0.7},
  "is_active": true
}
```

### 更新 (PATCH /api/llms/{id}/)
```json
{
  "extra": {"temperature": 0.2, "num_ctx": 4096}
}
```

## レスポンス例
### 一覧 (GET /api/llms/)
```json
[
  {
    "id": 1,
    "name": "Local Llama3",
    "provider": "OLLAMA",
    "base_url": "http://ollama:11434",
    "model": "llama3:8b",
    "extra": {"temperature": 0.2, "num_ctx": 4096},
    "is_active": true
  }
]
```

### 単一取得 (GET /api/llms/1/)
```json
{
  "id": 1,
  "name": "Local Llama3",
  "provider": "OLLAMA",
  "base_url": "http://ollama:11434",
  "model": "llama3:8b",
  "extra": {"temperature": 0.2},
  "is_active": true
}
```

### 作成成功 (201)
```json
{
  "id": 2,
  "name": "Test",
  "provider": "OLLAMA",
  "base_url": null,
  "model": "llama3:8b",
  "api_key": "***",   // Serializer 上は戻り値にも含まれる
  "extra": {},
  "is_active": true
}
```

## cURL サンプル
```bash
# 一覧
curl -s http://localhost:8000/api/llms/

# 作成 (CSRF / 認証不要構成の場合の例)
curl -X POST http://localhost:8000/api/llms/ \
  -H 'Content-Type: application/json' \
  -d '{"name":"Local","provider":"OLLAMA","model":"llama3:8b"}'
```

## バリデーション & 制約
- `name`, `model` は空不可
- `provider` は定義済み選択肢のみ
- `base_url` は形式検証なし（Docker Compose ホスト名を許容）
- `OPENAI` / `GEMINI` 選択時は `api_key` 必須

## エラー
| ステータス | 例 | 原因 |
|------------|----|------|
| 400 | {"provider":["\"XYZ\" is not a valid choice."]} | provider 不正 |
| 404 | - | 指定 ID が存在しない |
| 405 | - | 不正 HTTP メソッド |
| 500 | - | DB / サーバ内部エラー |

## セキュリティ注意
- `api_key` は現状平文保存。実運用では暗号化または外部 Secret 管理（例: HashiCorp Vault, AWS KMS）を推奨。
- OpenAI 等サードパーティ対応時は `provider` 毎のクライアント分離と送信ログマスクを検討。

## 将来拡張案
1. リトライ・レート制限ハンドリング (バックオフ)
2. `is_active=false` の論理削除運用（現状フィルタは LLM モデルでは行っていない）
3. OpenAPI / drf-spectacular による自動スキーマ生成
4. `extra` パラメータスキーマ制約（JSON Schema）
5. `api_key` マスキングレスポンス（"****"）
6. Gemini system メッセージ正式取り扱い（現状 user として送出）

---
最終更新: 自動生成後に検修
