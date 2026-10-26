# 認証 API

## 根拠・状態

- 要件と決定事項: [Issue #20 の計画書](../../design-docs/backend-session-authentication-issue-20.md)
- 本書は現在の認証 API 実装に基づく仕様である。
- レスポンス契約として、login・me は `200`、logout は `204`（空 body）、ログイン失敗は同一形式の `400`、未認証・期限切れで認証必須 API にアクセスした場合は `403` とする。

## 目的・対象

Django 標準 User を使い、管理者が Django Admin で作成した有効なユーザーにセッション認証を提供する。ユーザー登録 API、OAuth/SSO/MFA、パスワード再設定、ユーザーごとの業務データ分離は対象外とする。認証済みユーザー間では業務データを共有する。

## エンドポイント

| メソッド | パス | 概要 | 成功ステータス | 実装状況 |
| --- | --- | --- | --- | --- |
| POST | `/api/auth/login/` | ユーザー名・パスワードでログインし、Django セッションを開始する | 200 | 実装済み |
| POST | `/api/auth/logout/` | 現在の認証セッションを無効化する | 204 | 実装済み |
| GET | `/api/auth/me/` | ログイン中のユーザーとセッション有効期限を取得する | 200 | 実装済み |

パスは `/api/` を含む。末尾の `/` を付ける。ログイン・ログアウト以外の認証方式やトークン発行は提供しない。

## 認証・権限

- API 認証方式は Django セッション認証のみとし、Basic 認証は無効にする。
- 未認証で利用できる API は `GET /api/health/`、`GET /api/csrf/`、`POST /api/auth/login/` のみとする。ログアウト、`me`、DRF の `GET /api/` 一覧、その他すべての業務 API は認証を必須とする。
- 認証必須 API への未認証・ログアウト済み・期限切れセッションの要求は `403 Forbidden`。期限切れのセッションは認証済みとして扱わない。
- ログインおよびログアウトの POST は CSRF 検証を必須とする。CSRF 検証に失敗した場合は `403 Forbidden`。
- 認証済みユーザー間のリソース所有権による制限は設けない。
- Django Admin を含むすべての認証セッションに、ログイン時刻から固定 12 時間の絶対期限を適用する。`now >= login_time + 43,200 秒` で失効し、API や Admin の利用で期限を延長しない。

## 入力フィールド

### `POST /api/auth/login/`

| 項目 | 場所 | 型 | 必須 | 省略時 | null/空文字 | 制約 |
| --- | --- | --- | --- | --- | --- | --- |
| `username` | body | string | 必須 | 不可 | 不可 | Django 標準 User のユーザー名（最大 150 文字） |
| `password` | body | string | 必須 | 不可 | 不可 | Django の標準認証バックエンドで照合する。パスワードをトリム・再出力しない |

JSON オブジェクトを送る。Serializer に定義されていない追加フィールドは無視される。

### `POST /api/auth/logout/`、`GET /api/auth/me/`

Path/query/body パラメータは不要。logout の JSON body は送らない。

## リクエスト例

ログイン・ログアウトを含む unsafe method では、CSRF Cookie と `X-CSRFToken` ヘッダーを送る。CSRF トークンを得るには先に [CSRF API](csrf.md) を呼び出す。

Django はログイン成功時に CSRF トークンをローテーションする。ログイン後に logout などの unsafe method を呼ぶ前に、[CSRF API](csrf.md) から新しいトークンを取得し、更新された Cookie とともに使用する。

```http
POST /api/auth/login/
Content-Type: application/json
Accept: application/json
Cookie: csrftoken=<csrf-cookie>
X-CSRFToken: <masked-csrf-token>

{
  "username": "sample-user",
  "password": "example-password"
}
```

```http
GET /api/auth/me/
Accept: application/json
Cookie: sessionid=<session-cookie>
```

```http
POST /api/auth/logout/
Accept: application/json
Cookie: sessionid=<session-cookie>; csrftoken=<csrf-cookie>
X-CSRFToken: <masked-csrf-token>
```

ブラウザの `fetch` では、同一オリジンなら既定の `credentials: 'same-origin'`、クロスオリジンなら `credentials: 'include'` を指定して Cookie を送受信する。Cookie 値は例示であり、実際のセッション識別子や CSRF トークンをログへ記録しない。

## 成功レスポンス

### ログイン成功・`me`

どちらも `200 OK`。成功時のレスポンスは次の形とする。

```json
{
  "user": {
    "id": 12,
    "username": "sample-user"
  },
  "expires_at": "2026-10-27T05:00:00+00:00"
}
```

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `user` | object | 認証済みユーザーの公開情報 |
| `user.id` | integer | Django 標準 User の ID |
| `user.username` | string | ユーザー名 |
| `expires_at` | string | この認証セッションの絶対失効時刻。タイムゾーン付き ISO 8601 形式 |

レスポンスにパスワード、パスワードハッシュ、セッション識別子、CSRF トークンを含めない。`expires_at` はログイン成功時刻から 12 時間後で、後続リクエストによって変更しない。セッション Cookie はレスポンスヘッダーで設定する。Cookie の名前・属性は Django 設定に従い、アクセストークンを JSON で返さない。

### ログアウト成功

`204 No Content`。レスポンスボディは空。サーバー側のセッションを無効化し、セッション Cookie を失効させる。

## エラーレスポンス

| 条件 | ステータス | 応答形式・detail |
| --- | --- | --- |
| ユーザー名不明、パスワード誤り、無効ユーザー | 400 | `{"detail":"Invalid username or password."}` |
| 必須項目不足、型不正、空のユーザー名またはパスワード | 400 | Serializer の項目別エラー |
| CSRF 検証失敗 | 403 | Django の CSRF エラー応答 |
| 認証必須 API への未認証・期限切れアクセス | 403 | `{"detail":"Authentication credentials were not provided."}` |
| 未対応メソッド | 405 | DRF の標準エラー応答 |
| 未対応 Content-Type | 415 | DRF の標準エラー応答 |

認証失敗はユーザー名の存在有無で status・JSON 形状・メッセージを変えず、上表の同一の `400` 応答を返す。パスワードを含む入力値を応答やログへ出力しない。Serializer の入力エラーは DRF の項目別エラー形式で返す。

## 処理・副作用

- ログインは Django 標準認証バックエンドで資格情報を照合し、成功時にサーバー側セッションを開始する。パスワードは既存の Django 標準ハッシュ照合を使う。
- ログインフォーム送信時にも CSRF 検証を適用する。クライアントはログイン前に CSRF Cookie とトークンを取得する。
- ログアウトは現在のサーバー側セッションを無効化する。無効化後の Cookie の再送は認証として受け付けない。
- 固定期限は Django Admin と API の認証セッション双方に適用する。セッション Cookie のスライディング更新やアクセスによる期限延長を認めない。期限情報を持たない既存セッションは無効化し、再ログインを要求する。
- `SESSION_COOKIE_SECURE`、`CSRF_COOKIE_SECURE`、CSRF Cookie の HttpOnly 属性等は環境設定に依存する。HTTPS を使う外部環境では Secure 属性を有効にする。個々のデプロイ環境での設定値は本 API 契約では固定しない。

## 互換性・既存クライアントへの影響

この API と共通認証方針により、既存の匿名クライアントは認証必須の業務 API を利用できない。既存フロントエンドの認証対応は本書の対象外であり、現在の画面からの API 呼び出しは認証エラーとなる。フロントエンド対応を含む統合時期を別途調整する必要がある。

## 挙動・受け入れ条件

- 有効ユーザーはログインでき、`200 OK` と Django セッション Cookie、および上記 `user`・`expires_at` を受け取る。
- 不明なユーザー名、誤ったパスワード、無効ユーザーは同一の `400 Bad Request` と同一の `detail` を返す。パスワード・ハッシュはどの応答にも含めない。
- `me` は認証済みユーザーに限り上記の最小情報と絶対失効時刻を `200 OK` で返す。
- ログアウトは `204 No Content` を返し、レスポンス body は空とする。ログアウト後は同じセッション Cookie で保護 API を利用できない。
- 43,199 秒経過時点ではセッションが有効であり、43,200 秒到達時点では Django Admin を含め失効する。API 利用で期限を延長しない。
- health・csrf・login のみ匿名利用でき、logout、API 一覧、すべての業務 API は匿名・ログアウト済み・期限切れの状態で `403 Forbidden` により拒否される。
- すべての unsafe method（ログイン・ログアウトを含む）は CSRF 検証に失敗した場合に拒否される。
- Serializer の未知フィールドは無視される。必須項目不足・型不正は項目別のエラーを返す。
- Cookie の Secure 属性は環境設定に依存する。開発時の既定値は Secure 無効であり、HTTPS 環境では環境に合わせて有効化する。

## 運用上の注意

Django Admin で有効な標準 User を登録する。アプリ起動時の初期管理者設定は講義用ローカル環境向けであり、外部環境では使わない。初期管理者の固定パスワードは本計画では変更対象外だが、そのまま外部環境で稼働させてはならない。

## 実装参照

- 要件・決定事項: [Issue #20 の計画書](../../design-docs/backend-session-authentication-issue-20.md)
- [認証ルート](../../../backend/core/urls.py)
- [認証 View](../../../backend/core/auth_views.py)
- [ログイン入力 Serializer](../../../backend/core/serializers.py)
- [セッション期限ミドルウェア](../../../backend/core/authentication.py)
- [認証・Cookie 設定](../../../backend/lecture_system/settings.py)
- [認証 API テスト](../../../backend/core/tests/test_auth_api.py)
