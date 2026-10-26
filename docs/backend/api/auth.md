# 認証 API

**現行実装に基づく仕様**

> API契約は Issue #23 と [認証実装計画](../../design-docs/user-authentication-login-12-hour-session.md) に基づく。以下の3エンドポイントは実装済み。業務API全体の権限適用と固定期限の実装状況を記載する。

## 目的・対象

ユーザー名とパスワードでDjangoセッションにログインし、ログアウトおよび現在のログインユーザー・有効期限の確認を行う。ユーザーの登録・管理はDjango Adminで行う。

対象エンドポイントは次の3つ。パスは `/api/` を含む。

| メソッド | パス | 概要 | 成功ステータス | 実装状況 |
| --- | --- | --- | --- | --- |
| POST | `/api/auth/login/` | 資格情報を検証し、セッションを開始 | 200 | 実装済み |
| POST | `/api/auth/logout/` | 現在の認証セッションを無効化 | 204 | 実装済み |
| GET | `/api/auth/me/` | ログインユーザーと固定有効期限を取得 | 200 | 実装済み |

URL末尾の `/` を必須とする。末尾スラッシュなしの更新系リクエストでリダイレクトを前提にしない。未対応メソッドは `405 Method Not Allowed`。

## 根拠と現行実装

### 要件（Issue #23）

- Django標準のユーザー認証とセッションを利用し、Adminで管理する。
- 認証失敗時、ユーザー名が存在するかを応答から判別できないようにする。
- パスワード・ハッシュはAPIレスポンスに含めない。
- ログイン成功時から固定で12時間（43,200秒）有効とし、API操作で延長しない。
- ログインを含む更新系操作にCSRF対策を適用する。

### 実装内容

- `core/urls.py` は3つの認証ルートを登録している。
- DRFの既定認証は `FixedExpirySessionAuthentication`、権限は `IsAuthenticated`。ログインViewは匿名許可し、health/CSRFも匿名例外。
- `GET /api/csrf/` はCSRFトークンを返す既存APIであり、ログインやAPIトークンの発行は行わない。詳細は [CSRF API](csrf.md) を参照。
- `core/authentication.py` がログイン時刻から43,200秒を照合する。以下の実装説明はコードで確認した現行挙動である。

## 認証・権限

- 認証方式はDjangoセッション認証。JWT、Basic認証、独自APIトークンは使用しない。
- `login` は匿名で呼び出せるが、匿名状態でもCSRF検証を必須とする。
- `logout` と `me` は有効な認証セッションを必須とする。未認証・期限切れは `401 Unauthorized`。
- ログイン後のリソース権限・ユーザー所有権はこのAPI仕様の対象外。Issueの範囲では、認証済みユーザー間でLLM、会話、Agent、Datasource等の既存データを共有する。
- `/api/csrf/` と `/api/health/` は匿名アクセス可能。その他の業務APIは認証必須。
- セッションCookieのSecure等はDjango設定に従う。開発既定ではSecure=falseであり、本番HTTPS環境の設定が必要。

### CSRFの扱い

1. クライアントは先に `GET /api/csrf/` を呼び出し、CSRF Cookieを受け取る。
2. `POST /api/auth/login/` と `POST /api/auth/logout/` にはCookieと `X-CSRFToken` ヘッダーを送る。
3. CSRF検証失敗時は `403 Forbidden`。`csrf_protect` の既定応答を使うため、本文はJSON形式を保証しない。
4. ログイン成功時にDjangoがセッションキーをローテーションする。CSRFトークンもログイン前後に更新される場合がある。

## 入力フィールド

| 項目 | 場所 | 型 | 必須 | 省略時 | null/空文字 | 制約 |
| --- | --- | --- | --- | --- | --- | --- |
| `username` | login body | string | 必須 | なし | null・空文字は禁止 | Django標準Userの最大150文字。前後空白は除去しない。 |
| `password` | login body | string | 必須 | なし | null・空文字は禁止 | Djangoのパスワード検証にそのまま渡す。前後空白を除去しない。 |
| `Cookie` | login/logout/me header | Cookie | セッションがある場合 | 匿名時はなし | 該当なし | Django session cookie。名前は既定設定を変更しない場合 `sessionid`。 |
| `X-CSRFToken` | login/logout header | string | login/logoutで必須 | なし | 空文字は禁止 | `/api/csrf/` で取得したCSRF Cookieに対応するトークン。 |

`login` は `application/json` のオブジェクトを受け付け、JSON以外は415、JSON配列等の非オブジェクトは400とする。追加フィールドは無視する。`logout` と `me` はリクエストボディ不要。

## リクエスト例

### ログイン

事前に [CSRF API](csrf.md) を呼び出してCookieを取得する。資格情報はTLSで送信し、URL・クエリパラメーターには含めない。

```http
POST /api/auth/login/ HTTP/1.1
Content-Type: application/json
Accept: application/json
Cookie: csrftoken=<csrf-cookie>
X-CSRFToken: <csrf-token>

{
  "username": "student01",
  "password": "example-password"
}
```

### ログアウト

```http
POST /api/auth/logout/ HTTP/1.1
Accept: application/json
Cookie: sessionid=<session-cookie>; csrftoken=<csrf-cookie>
X-CSRFToken: <csrf-token>
```

### 現在のユーザー

```http
GET /api/auth/me/ HTTP/1.1
Accept: application/json
Cookie: sessionid=<session-cookie>
```

## 成功レスポンス

### `POST /api/auth/login/` — `200 OK`

ログイン成功時、DjangoセッションCookieを `Set-Cookie` で返し、本文には必要最小限の公開ユーザー情報とUTC有効期限を返す。

```json
{
  "user": {
    "id": 7,
    "username": "student01"
  },
  "expires_at": "2026-10-26T17:00:00Z"
}
```

### `POST /api/auth/logout/` — `204 No Content`

セッションをサーバー側で無効化し、セッションCookieを削除する `Set-Cookie` を返す。レスポンスボディは空とする。

### `GET /api/auth/me/` — `200 OK`

```json
{
  "user": {
    "id": 7,
    "username": "student01"
  },
  "expires_at": "2026-10-26T17:00:00Z"
}
```

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `user` | object | 認証済みユーザーの公開情報。 |
| `user.id` | integer | Djangoユーザーの主キー。 |
| `user.username` | string | Djangoユーザー名。 |
| `expires_at` | string (date-time) | ログイン成功時から43,200秒後のUTC時刻。ISO 8601形式の `Z` 表記。 |

パスワード、パスワードハッシュ、セッションキー、CSRFトークンは本文に含めない。`expires_at` はログイン時に確定し、以後のリクエストで更新しない。

## エラーレスポンス

| 条件 | ステータス | 応答形式 | 備考 |
| --- | --- | --- | --- |
| loginの資格情報不足・空文字・形式不正 | 400 | `{"detail":"Invalid request."}` | JSON object以外、username/passwordがない・空・文字列でない場合。 |
| usernameが最大長を超える | 400 | `{"detail":"Invalid request."}` | Django Userのusername最大長（150）を超える場合。 |
| ユーザー名またはパスワードが不正、無効ユーザー | 401 | `{"detail":"Invalid username or password."}` | 資格情報の組合せが異なる場合も同じステータス・本文。 |
| logout/meで未認証 | 401 | DRFの `detail` エラー | 実際のdetail文言はDRF設定に依存する。 |
| セッション期限切れ | 401 | `{"detail":"Authentication expired."}` | セッションを無効化し、保護対象APIへの処理を行わない。 |
| login/logoutのCSRF検証失敗 | 403 | Django標準のCSRF失敗応答 | HTML等になる場合があり、JSON形式は保証しない。 |
| 未対応メソッド | 405 | DRFの `detail` エラー | `Allow` ヘッダーを含む。 |
| 未対応Content-Type | 415 | DRF形式のエラー | JSON以外のlogin bodyは受理しない。 |

DRF標準エラー文言はバージョン・設定に依存する。サーバー障害など予期しない例外については、JSON形式や本文を保証しない。

## 処理・副作用

### ログイン

1. CSRFを検証する。
2. `username` / `password` をDjango標準認証バックエンドで検証する。資格情報不正とユーザー不在の応答を同一にする。
3. 認証成功時に既存の匿名セッションを引き継がずセッションキーをローテーションし、ログイン時刻をサーバー側セッションに記録する。
4. `expires_at = login_time + 43,200秒` を決定し、以後のAPI操作では変更しない。
5. 認証成功応答を返す。ユーザーの作成・更新は行わない。

### ログアウト

認証済みセッションをDjangoのログアウト処理でサーバー側から無効化し、以後そのCookieで保護APIを利用できないようにする。未認証または期限切れの場合は401となる。

### 有効期限の検査

- サーバー側の時刻を基準にし、`now >= expires_at` なら期限切れとする。時刻はUTC基準。
- 認証済み状態を使うすべての保護APIで期限を検査し、期限切れならセッションを無効化して401を返す。フロントエンドのタイマーだけに依存しない。
- 期限時刻は最終操作時刻ではない。リクエストによる延長・再発行を行わない。
- 有効期限はDjangoセッション内のログイン時刻から算出する。`session.set_expiry(43_200)` も設定する。期限検査はアプリAPIのセッション認証に適用される。

## 互換性・変更案

| 観点 | 現行 | 変更案 | 影響 |
| --- | --- | --- | --- |
| 認証APIルート | login/logout/meは存在しない | 上記3ルートを追加 | 新規APIのため既存ルートのパスは変更しない。 |
| 業務APIアクセス | 現状は未認証アクセス可能 | 認証・固定期限を適用 | 既存の匿名クライアントはログイン導入後に認証必須となる。全フロントを同一リリースで更新する必要がある。 |
| セッション期限 | 本APIの固定期限契約はない | ログインから43,200秒 | Django Adminとのセッション共有やCookie設定との影響を実装前に確認する。 |
| リソース所有権 | ユーザー単位の所有者関連付けなし | 今回も追加しない | ログイン後もユーザー間でデータが共有される。 |

## 受け入れ条件・検討事項

### 仕様受け入れ条件

- 有効なAdmin登録ユーザーはログインでき、無効な資格情報はユーザー名の有無を判別できない同一の失敗応答となる。
- login成功とmeの応答はユーザーID、ユーザー名、有効期限のみを含み、資格情報・ハッシュ・セッションキーを含まない。
- logout後のセッションCookieは無効であり、logout/meまたは保護APIは以後認証を認めない。
- ログイン直後から43,200秒未満は有効、`now == expires_at` 以降は無効。アクセス継続でも期限は延長されない。
- login/logoutはCSRFを要求し、CSRF失敗を認証失敗と混同しない。

### 未確定事項・運用上の注意

1. CSRF失敗応答はDjango標準でありJSON形式を保証しない。授業UIがJSONだけを想定する場合は別途failure handlerを検討する。
2. CSRF CookieのSecure/SameSite属性は環境設定に依存する。HTTPS環境でSecureを有効化する運用を前提とする。
3. APIの12時間期限とDjango Adminのログイン期限は同一制御ではない。Adminにも同じ絶対期限を適用する要件はIssueにない。
4. 認証失敗へのrate limit/アカウントロックはIssueで明示されていないため、この実装には含めていない。

## 実装参照

- [Issue #23](https://github.com/MHonda119/special-software-plactice-2026/issues/23) — 認証API・固定12時間期限の要件。
- [認証実装計画](../../design-docs/user-authentication-login-12-hour-session.md) — 仕様検討の入力。計画文書であり実装済みを意味しない。
- [API URL定義](../../../backend/core/urls.py) — 現行ルート。認証APIは未登録。
- [認証View](../../../backend/core/auth_views.py) — login/logout/meの実装。
- [認証クラス](../../../backend/core/authentication.py) — 12時間の固定期限検証。
- [Django設定](../../../backend/lecture_system/settings.py) — auth/session/CSRF関連設定。
- [CSRF API](csrf.md) — 現行CSRFトークン取得仕様。
