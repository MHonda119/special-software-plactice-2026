# Backend API仕様書

Django REST Frameworkで実装されているAPIの仕様を、リソース別にまとめる。各仕様書はCRUDだけでなく、チャット・エージェント実行・チャンク操作も含む。

本資料は現在のルート、View、Serializer、Model、ユースケースの実装を根拠とする。未実装の機能や期待する将来の動作を、現在の仕様としては記載しない。

仕様書一覧には、実装済みAPIの現行仕様に加えて仕様検討中のDraftを含む場合がある。Draftは未実装であり、公開済みエンドポイント一覧には含めない。

## 仕様書一覧

| API | 仕様書 | 主な機能 |
| --- | --- | --- |
| ヘルスチェック | [health.md](health.md) | HTTP応答の確認 |
| CSRF | [csrf.md](csrf.md) | CSRFトークンとCookieの発行 |
| 認証 | [auth.md](auth.md) | セッションログイン、ログアウト、現在ユーザーの取得 |
| LLM | [llms.md](llms.md) | 接続先・モデル・認証情報の管理 |
| セッション | [sessions.md](sessions.md) | 会話セッションのCRUD、履歴取得、チャット |
| エージェント | [agents.md](agents.md) | エージェントのCRUD、BASIC_CHAT/RAG_CHATの実行 |
| データソース | [datasources.md](datasources.md) | データソースのCRUD、チャンク登録・一覧・削除 |

## エンドポイント一覧

パスはバックエンドから見たURL。`{id}` は整数ID、`{uuid}` はセッションのUUID、`{chunk_id}` はチャンク識別子。

| メソッド | パス | 概要 | 仕様書 |
| --- | --- | --- | --- |
| GET | `/api/` | DRFが自動生成するリソースへのリンク一覧 | 本書 |
| GET | `/api/health/` | ヘルスチェック | [health.md](health.md) |
| GET | `/api/csrf/` | CSRFトークン取得 | [csrf.md](csrf.md) |
| POST | `/api/auth/login/` | セッションログイン | [auth.md](auth.md) |
| POST | `/api/auth/logout/` | セッションログアウト | [auth.md](auth.md) |
| GET | `/api/auth/me/` | 現在のログインユーザー | [auth.md](auth.md) |
| GET | `/api/llms/` | LLM一覧 | [llms.md](llms.md) |
| POST | `/api/llms/` | LLM作成 | [llms.md](llms.md) |
| GET | `/api/llms/{id}/` | LLM詳細 | [llms.md](llms.md) |
| PUT | `/api/llms/{id}/` | LLM更新 | [llms.md](llms.md) |
| PATCH | `/api/llms/{id}/` | LLM部分更新 | [llms.md](llms.md) |
| DELETE | `/api/llms/{id}/` | LLM削除 | [llms.md](llms.md) |
| GET | `/api/sessions/` | セッション一覧 | [sessions.md](sessions.md) |
| POST | `/api/sessions/` | セッション作成 | [sessions.md](sessions.md) |
| GET | `/api/sessions/{uuid}/` | セッション詳細 | [sessions.md](sessions.md) |
| PUT | `/api/sessions/{uuid}/` | セッション更新 | [sessions.md](sessions.md) |
| PATCH | `/api/sessions/{uuid}/` | セッション部分更新 | [sessions.md](sessions.md) |
| DELETE | `/api/sessions/{uuid}/` | セッション削除 | [sessions.md](sessions.md) |
| GET | `/api/sessions/{uuid}/messages/` | メッセージ履歴取得 | [sessions.md](sessions.md) |
| POST | `/api/sessions/{uuid}/chat/` | チャット実行 | [sessions.md](sessions.md) |
| GET | `/api/agents/` | エージェント一覧 | [agents.md](agents.md) |
| POST | `/api/agents/` | エージェント作成 | [agents.md](agents.md) |
| GET | `/api/agents/{id}/` | エージェント詳細 | [agents.md](agents.md) |
| PUT | `/api/agents/{id}/` | エージェント更新 | [agents.md](agents.md) |
| PATCH | `/api/agents/{id}/` | エージェント部分更新 | [agents.md](agents.md) |
| DELETE | `/api/agents/{id}/` | エージェント削除 | [agents.md](agents.md) |
| POST | `/api/agents/{id}/execute/` | エージェント実行 | [agents.md](agents.md) |
| GET | `/api/datasources/` | データソース一覧 | [datasources.md](datasources.md) |
| POST | `/api/datasources/` | データソース作成 | [datasources.md](datasources.md) |
| GET | `/api/datasources/{id}/` | データソース詳細 | [datasources.md](datasources.md) |
| PUT | `/api/datasources/{id}/` | データソース更新 | [datasources.md](datasources.md) |
| PATCH | `/api/datasources/{id}/` | データソース部分更新 | [datasources.md](datasources.md) |
| DELETE | `/api/datasources/{id}/` | データソース削除 | [datasources.md](datasources.md) |
| GET | `/api/datasources/{id}/chunks/` | チャンク一覧 | [datasources.md](datasources.md) |
| POST | `/api/datasources/{id}/chunks/` | チャンク登録 | [datasources.md](datasources.md) |
| DELETE | `/api/datasources/{id}/chunks/{chunk_id}/` | チャンク削除 | [datasources.md](datasources.md) |

ViewSetではGETに対応するHEAD、各APIではOPTIONSなどのDRF標準機能も利用できる。表は業務操作としてのメソッドを示す。`/admin/` はDjango管理画面であり、本資料のREST API対象外。

## 接続・形式

- バックエンドへ直接接続する場合の開発用ベースURLは `http://localhost:8000/api/`。
- フロントエンドからは同一オリジンの `/api/` を利用できる。開発環境の設定は [セットアップ手順](../../setup.md) を参照。
- URL末尾の `/` を付ける。スラッシュ省略時のリダイレクトを更新系リクエストで前提としない。
- リクエスト例は `Content-Type: application/json`、レスポンスは `Accept: application/json` を前提とする。ブラウザではDRFのBrowsable APIが表示される場合もある。
- ID・UUID・日時・生成テキスト・usageの値は例示であり固定値ではない。日時はシリアライズされたISO 8601形式。
- 自前のストリーミングレスポンスは実装していない。チャットも処理完了後にJSONを返す。`options.stream=true` によるSSE利用はサポートしない。

## 現行実装の認証・CSRF

DRFの既定認証は固定12時間期限を検査するセッション認証、既定権限は `IsAuthenticated`。

- `/api/auth/login/` と `/api/csrf/`、`/api/health/` は匿名アクセス可能。logout/meと業務APIは認証を必須とする。
- login/logoutのセッションCookieを使うPOSTではCSRF検証が行われる。[CSRF API](csrf.md) でCookieを受け取り、`X-CSRFToken` ヘッダーを送る。
- ログイン時刻から43,200秒でセッション認証を失効させる。業務APIの操作で期限は延長されない。
- JWT、Basic認証、独自APIトークンは使用しない。LLMの `api_key` は外部プロバイダ向けであり、本APIの認証トークンではない。
- 認証済みユーザー間のリソース所有権チェックはなく、LLM等の業務データは共有される。
- 外部公開時のCookie/CSRF/HTTPS設定を適切に構成する。LLMの書き込みレスポンスには外部APIキーが含まれるため、ログにも注意する。

エンドポイントごとの入出力は [認証 API](auth.md) を参照。

## CRUD共通仕様

| 操作 | 成功ステータス | レスポンス |
| --- | --- | --- |
| 一覧・詳細取得 | 200 | 配列・オブジェクト |
| 作成 | 201 | 作成後のオブジェクト |
| PUT/PATCH | 200 | 更新後のオブジェクト |
| 削除 | 204 | ボディなし |

- PUTは各Serializerの必須入力項目を要求し、PATCHは指定項目だけを更新する。PUTでも、省略した任意項目を一律に初期化する実装ではない。
- JSON項目の更新は項目全体の置換であり、既存オブジェクトとの再帰的なマージではない。実行時のLLMオプションのマージとは区別する。
- 通常のリソース一覧はページングなしの配列。検索・任意フィルター・並べ替えのAPIパラメータは未実装で、順序も指定されていない。メッセージ履歴の順序とチャンク一覧の `limit`/`offset` は個別仕様を参照。
- 関連LLMをIDで指定する際は存在のみを検証し、`LLM.is_active` による選択制限は行わない。
- DELETEは原則として物理削除。`is_active` の変更による非表示化とは異なる。対象範囲・関連データへの影響は各仕様書を参照。

## エラー共通仕様

入力項目の検証エラーは通常 `400 Bad Request` で、項目名をキーとしたメッセージ配列を返す。

```json
{
  "name": ["This field is required."]
}
```

処理単位のエラーでは `detail` を返す場合がある。

```json
{
  "detail": "message is required"
}
```

| ステータス | 主な条件 |
| --- | --- |
| 400 | 入力検証失敗、不正なJSON、不正なパラメータ |
| 403 | セッション認証時のCSRF検証失敗、認証失敗など |
| 404 | 通常の詳細取得対象が存在しない、個別に定義された非アクティブ・所属不一致条件 |
| 405 | 未対応のHTTPメソッド |
| 415 | 未対応のリクエストContent-Type |
| 422 | チャンクの埋め込み生成失敗、特定のRAG設定エラー。個別仕様を参照 |
| 500 | 未処理例外、個別に捕捉しているストア処理失敗など |

存在しない外部キーIDを作成・更新の入力に渡した場合は、通常は `404` ではなくSerializerの `400`。DRF標準エラーの文言はバージョン・言語設定に依存する。

未処理例外に統一JSONエラーを返す独自ハンドラーはない。外部LLMの失敗を `502`/`504` に変換したり、参照中LLMの削除失敗を `409` に変換したりする処理もない。`500` のボディがJSONになることは保証しない。セッションチャットの存在確認も独自実装のため、通常CRUDの `404` と異なる点に注意する。

## APIルート

`GET /api/` は `DefaultRouter` の自動生成レスポンス。リクエストボディは不要で、成功時は `200 OK`。返却URLのホスト・スキームはリクエストやプロキシ設定に依存する。

```json
{
  "llms": "http://localhost:8000/api/llms/",
  "sessions": "http://localhost:8000/api/sessions/",
  "agents": "http://localhost:8000/api/agents/",
  "datasources": "http://localhost:8000/api/datasources/"
}
```

`health` と `csrf` はルーター外で明示登録されているため、この一覧には含まれない。

## 実装参照

- [プロジェクトのURL定義](../../../backend/lecture_system/urls.py)
- [APIのURL定義](../../../backend/core/urls.py)
- [View・アクション](../../../backend/core/views.py)
- [Serializer・入力検証](../../../backend/core/serializers.py)
- [Model・関連データの削除制約](../../../backend/core/models.py)
- [認証・ミドルウェア等の設定](../../../backend/lecture_system/settings.py)
- [既存のAPI設計資料](../../../backend/documents/)
