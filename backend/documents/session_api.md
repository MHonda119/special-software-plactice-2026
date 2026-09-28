# Chat Session API ドキュメント

> 注記: 指示にあった `bacjend/documents` は typo と判断し `backend/documents` に配置。

## 概要
チャット用のセッションを管理し、メッセージ履歴参照および LLM への問い合わせ(チャット)を実行する API です。セッションは特定の LLM (`llm` 外部キー) に紐づき、ユーザメッセージとアシスタントレスポンスが `Message` として永続化されます。

ベースパス: `/api/sessions/`

## 関連モデル
### ChatSession
| フィールド | 型 | 説明 |
|-----------|----|------|
| uuid | UUID | プライマリキー（URL で利用）|
| llm | integer | `LLM` モデル ID 参照 (FK, `PROTECT`) |
| title | string(<=200) | セッションタイトル（デフォルト `New Session`）|
| metadata | JSON | （内部利用予定 / Serializer 未露出）|
| is_active | bool | Active フィルタ用（ViewSet は `is_active=True` のみ）|
| created_at | datetime | 作成日時 |
| updated_at | datetime | 更新日時 |

### Message (一部のみ公開)
| フィールド | 型 | 説明 |
|-----------|----|------|
| id | integer | 自動採番 |
| role | enum | `system` / `user` / `assistant` / `tool` |
| content | text | メッセージ本文 |
| created_at | datetime | 生成日時 |

## シリアライザ
- `ChatSessionCreateSerializer`: フィールド `uuid (read_only)`, `llm`, `title`
- `MessageSerializer`: フィールド `id`, `role`, `content`, `created_at`

## エンドポイント一覧
| メソッド | パス | 説明 |
|----------|------|------|
| GET | /api/sessions/ | アクティブセッション一覧取得 |
| POST | /api/sessions/ | セッション作成 |
| GET | /api/sessions/{uuid}/ | セッション取得 |
| PUT | /api/sessions/{uuid}/ | セッション全更新 (title / llm) |
| PATCH | /api/sessions/{uuid}/ | セッション部分更新 |
| DELETE | /api/sessions/{uuid}/ | 物理削除（関連 Message も CASCADE）|
| GET | /api/sessions/{uuid}/messages/ | セッション内メッセージ一覧取得（昇順 / 全履歴）|
| POST | /api/sessions/{uuid}/chat/ | メッセージ送信 + LLM 応答生成 |

## 典型フロー
1. LLM が存在していることを確認 (`/api/llms/`)
2. セッション作成 (`POST /api/sessions/`)
3. チャット送信 (`POST /api/sessions/{uuid}/chat/`)
4. 過去履歴確認 (`GET /api/sessions/{uuid}/messages/`)

## リクエスト / レスポンス詳細
### 1. セッション作成 (POST /api/sessions/)
リクエスト:
```json
{
  "llm": 1,
  "title": "Doc Test Session"
}
```
レスポンス (201):
```json
{
  "uuid": "2f52c5c5-5e2d-4f4a-8b3d-6b6d4d0d0e11",
  "llm": 1,
  "title": "Doc Test Session"
}
```

### 2. セッション一覧 (GET /api/sessions/)
```json
[
  {"uuid":"2f52c5c5-...","llm":1,"title":"Doc Test Session"}
]
```

### 3. メッセージ一覧 (GET /api/sessions/{uuid}/messages/)
```json
[
  {"id":10,"role":"user","content":"こんにちは","created_at":"2025-10-26T02:34:51Z"},
  {"id":11,"role":"assistant","content":"こんにちは！ご用件は？","created_at":"2025-10-26T02:34:52Z"}
]
```

### 4. チャット送信 (POST /api/sessions/{uuid}/chat/)
リクエスト:
```json
{
  "message": "Explain RAG simply.",
  "options": {"temperature": 0.3}
}
```
処理内容:
1. `user` メッセージ保存
2. これまでの全メッセージを LLM クライアントに渡す (`client.chat`)
3. 返信を `assistant` として保存
4. 最後のアシスタントメッセージと usage を返却

レスポンス (200):
```json
{
  "session_uuid": "2f52c5c5-5e2d-4f4a-8b3d-6b6d4d0d0e11",
  "assistant_message": {
    "id": 12,
    "role": "assistant",
    "content": "RAG は Retrieval Augmented Generation の略で ..."
  },
  "usage": {"eval_count": 1234}
}
```

### 5. チャット入力バリデーションエラー
`message` が空 or 未指定
```json
{"detail": "message is required"}
```
ステータス: 400

## cURL 例
```bash
# セッション作成
curl -s -X POST http://localhost:8000/api/sessions/ \
  -H 'Content-Type: application/json' \
  -d '{"llm":1, "title":"Demo"}'

# チャット送信
curl -s -X POST http://localhost:8000/api/sessions/<UUID>/chat/ \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hello"}'

# メッセージ履歴
curl -s http://localhost:8000/api/sessions/<UUID>/messages/
```

## エラー一覧
| ステータス | エンドポイント | 例 | 原因 |
|------------|----------------|----|------|
| 400 | POST /chat | {"detail":"message is required"} | message 未指定/空文字 |
| 404 | 任意 | - | uuid / セッション存在しない or is_active=False |
| 500 | /chat | - | LLM 呼び出し失敗 (HTTP エラー / JSON パース) |
| 504? | /chat | - | タイムアウト (requests.post timeout=120 超過) |

## タイミング・順序
`/chat/` 実行時は DB トランザクション内で `user` → LLM 呼び出し → `assistant` 永続化が一貫して行われます（`transaction.atomic`）。LLM 側で例外が起きた場合、ユーザーメッセージもロールバックされます。

## 並行性 / 整合性メモ
- 高頻度同時 POST `/chat/` を想定する場合、直列化 (行ロック / メッセージ最新取得方式変更) を将来検討。
- 現状: 全履歴取得は `session.messages.all()` の昇順結果。メッセージ数が増加するとパフォーマンス課題（ページング未実装）。

## セキュリティ / CSRF
- 認証未実装。外部公開する場合は Token / Session 認証追加推奨。
- CSRF: Cookie + `X-CSRFToken` ヘッダ（`/api/csrf/` で取得）を POST/PUT/PATCH/DELETE で送信。

## 限界・改善余地
| 項目 | 現状 | 改善案 |
|------|------|--------|
| ページング | なし | DRF Pagination 追加 (`messages`) |
| ストリーミング | 非対応 | サーバサイドイベント / chunk 送信 |
| usage 情報 | eval_count のみ | トークン数, 所要時間など拡張 |
| options マージ | `extra` + 呼び出し引数 | スキーマ定義/バリデーション追加 |
| セッション終了 | is_active フィールドのみ未利用 | 終了 API / アーカイブ状態追加 |

## バージョニング提案
- 今後の後方互換性維持のため `/api/v1/` プレフィックス化を検討。

## 監視指標例
- 1分あたりチャットリクエスト数
- LLM 呼び出し平均/95% レイテンシ
- 失敗率 (5xx / 全体)

---
最終更新: 自動生成後に検修
