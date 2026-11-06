# 認証 API

この文書は現行実装の仕様を示す。認証は Django 標準ユーザーとセッション Cookie を利用する。

## 目的・対象

Django 標準ユーザーを使ったセッション認証を提供する。対象はログイン、ログアウト、ログイン中ユーザー情報の取得、および業務 API の認証保護。ユーザー登録 API/UI、OAuth/SSO、MFA、パスワード再設定は提供しない。

すべての業務 API 操作に認証を要求する。health と CSRF トークン取得は公開し、login は匿名で利用できるが CSRF 検証を必須とする。

## エンドポイント

| メソッド | パス | 概要 | 成功ステータス | 実装状況 |
| --- | --- | --- | --- | --- |
| POST | `/api/auth/login/` | username/password でログインし、セッションを開始する | 200 | 実装済み |
| POST | `/api/auth/logout/` | 現在のセッションを終了する | 204 | 実装済み |
| GET | `/api/auth/me/` | ログイン中のユーザーとセッション期限を取得する | 200 | 実装済み |

すべて末尾に `/` を付ける。`/api/` はベースパスであり、認証 API の URL は `/api/auth/.../`。`/api/auth/` の一覧ルートは提供しない。

## 認証・権限

| API / 操作 | 未認証 | 認証済み | CSRF |
| --- | --- | --- | --- |
| `POST /api/auth/login/` | 利用可能 | 利用可能（再ログイン可） | 必須。匿名時も検証する |
| `POST /api/auth/logout/` | `401` | 利用可能 | 必須 |
| `GET /api/auth/me/` | `401` | 利用可能 | 不要 |
| `GET /api/health/`・`GET /api/csrf/` | 公開例外 | 利用可能 | 不要 |
| その他の業務 API（API root と DRF の標準操作を含む） | `401` | 利用可能 | unsafe method では必須 |

- Django 標準の session authentication を使い、ブラウザーはセッション Cookie を保持・送信する。セッション Cookie 以外の認証 token は発行しない。
- login は Django 標準の username/password 認証を使う。Django Admin で作成・管理する有効ユーザーを対象とし、登録 API/UI は設けない。
- login 成功時にサーバー側セッションへ固定の絶対期限を記録する。ログイン成功時刻から **43,200 秒（12 時間）** 経過した時点で失効し、アクセスやセッション更新では延長しない。境界時刻（`now >= expires_at`）以降は `me` と保護 API を拒否する。
- 認証済みユーザー間のリソース所有権・ユーザー別データ分離は対象外。
- Cookie の `Secure` は HTTPS 環境で有効にする。現設定は `DJANGO_SESSION_COOKIE_SECURE` 等の環境変数で Secure 属性を切り替えるが、開発向け既定値は `false`。本番では TLS 終端を含む環境設定を確認する。Cookie 属性の追加変更は未確定。

### CSRF の取得と送信

クライアントは先に [`GET /api/csrf/`](csrf.md) を呼び、Cookie を保持したまま login/logout および認証済みの更新リクエストへ `X-CSRFToken` を送る。Django の login は CSRF token をローテーションするため、ログイン後に再度 `/api/csrf/` を呼び、更新された token を使う。login は匿名でも CSRF 検証を行う。login の CSRF 検証失敗は `403` と JSON の `detail` を返し、認証済みの unsafe request も `SessionAuthentication` による CSRF 検証を受ける。詳細は [CSRF API](csrf.md) を参照。

## 入力

### `POST /api/auth/login/`

`Content-Type: application/json` の JSON object を受け取る。

| 項目 | 場所 | 型 | 必須 | 省略時 | null/空文字 | 制約 |
| --- | --- | --- | --- | --- | --- | --- |
| `username` | body | string | 必須 | 不可 | null・空文字不可 | Django 標準 User の username（最大150文字）。前後の空白を自動除去しない |
| `password` | body | string | 必須 | 不可 | null・空文字不可 | Django 標準認証に渡すパスワード。前後の空白を自動除去しない |

余分なフィールドは認証に使わず無視する。パスワード強度バリデーションは登録・変更時の責務であり、ログイン時に別の強度条件を適用しない。

### `POST /api/auth/logout/`、`GET /api/auth/me/`

Path/query/body パラメーターはない。logout の body は不要。GET の body は使用しない。

## リクエスト例

```http
GET /api/csrf/ HTTP/1.1
Host: localhost:8000
Accept: application/json
```

`/api/csrf/` が返す `csrftoken` Cookie を保持し、レスポンスの `csrftoken` 値を login の header に設定する。ログイン後は token がローテーションされるため、更新 API を呼ぶ前に `/api/csrf/` を再取得する。

```http
POST /api/auth/login/ HTTP/1.1
Host: localhost:8000
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
GET /api/auth/me/ HTTP/1.1
Host: localhost:8000
Accept: application/json
Cookie: sessionid=<session-cookie>
```

```http
POST /api/auth/logout/ HTTP/1.1
Host: localhost:8000
Accept: application/json
Cookie: sessionid=<session-cookie>; csrftoken=<csrf-cookie>
X-CSRFToken: <masked-csrf-token>
```

## 成功レスポンス

### `POST /api/auth/login/` — `200 OK`

認証成功時はセッション Cookie を設定し、`me` と同じ JSON object を返す。

### `GET /api/auth/me/` — `200 OK`

```json
{
  "user": {
    "id": 17,
    "username": "sample-user"
  },
  "expires_at": "2026-11-05T07:00:00Z"
}
```

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `user` | object | ログイン中のユーザー |
| `user.id` | integer | Django 標準 User の主キー |
| `user.username` | string | Django 標準 User の username |
| `expires_at` | string | セッションの絶対有効期限。UTC の ISO 8601/RFC 3339 日時（`Z` 表記）。login 成功時刻から 43,200 秒後 |

パスワード、パスワードハッシュ、セッションキー、CSRF token、メールアドレス等は返さない。例のユーザーと日時は架空。

### `POST /api/auth/logout/` — `204 No Content`

ログアウト成功時はサーバー側の現在の認証セッションを破棄し、空の body を返す。セッション Cookie を失効させる。未認証状態での logout は認証必須のため `401`。2 回目の logout も `401` となり、成功扱いする冪等動作ではない。

## エラーレスポンス

| 条件 | ステータス | 応答形式・例 |
| --- | --- | --- |
| login の username/password が誤り、ユーザーが存在しない、または無効 | 401 | `{"detail":"Invalid username or password."}` |
| login body の必須項目不足、型不正、null、空文字 | 400 | 項目名をキーとする検証エラー |
| 不正な JSON | 400 | JSON parser のエラー応答 |
| 認証必須 API にセッションがない、または期限切れ | 401 | `{"detail":"Authentication required."}` |
| login/logout/認証済み unsafe request の CSRF 検証失敗 | 403 | JSON の `detail`。CSRF failure の理由を含む |
| 未対応メソッド | 405 | DRF の method-not-allowed response |
| 未対応 Content-Type | 415 | DRF の unsupported-media-type response |

有効な username と無効なパスワード、存在しない username、無効ユーザーの認証失敗では、status、response body、本文の形を同じにして username の存在を推測できないようにする。資格情報・パスワードハッシュはエラー応答やログへ含めない。login 失敗時のレート制限は実装していない。

## 処理・副作用

1. login 成功時に Django 標準認証を行い、標準 login 処理でセッションキーを更新してセッション固定攻撃対策を維持する。
2. 固定期限の開始時刻と期限をサーバー側セッションに関連付け、期限はログイン時刻 + 43,200 秒で算出する。セッションのアイドル期限や Cookie の期限だけを認証期限として扱わない。
3. 保護 API は各リクエストでサーバー側の期限を検証する。期限到達時はセッションを無効化し、同じ Cookie を再送しても認証を復活させない。
4. `expires_at` とサーバーの期限判定は同じ絶対時刻に基づく。クライアント時計を期限判定に使用しない。
5. logout は Django 標準 logout により現在の session data を破棄する。期限切れ処理・logout に外部サービス呼び出しはない。

## 互換性

| 観点 | 実装前 | 現在 | 影響 |
| --- | --- | --- | --- |
| 認証エンドポイント | 未実装 | login/logout/me | 新規契約 |
| 業務 API 認証 | DRF の明示的な認証・権限設定なし | health/CSRF 取得と login を除き認証必須 | 匿名利用中のクライアントはログイン対応が必要 |
| セッション期限 | 認証 API なし | login 起点で固定 12 時間 | 期限後は再ログインが必要 |
| CSRF | Django middleware が有効。匿名 login の対象ルートはない | login も匿名時から CSRF 必須 | クライアントは CSRF 取得と Cookie 保持が必要 |

認証必須化は実装前の匿名クライアントに対して互換性のない変更となる。Django Admin のログインは管理画面で利用できるが、認証 API は login endpoint で発行した期限付きセッションだけを受け付ける。認証済みユーザー間の共有データの扱いは変わらない。

## 受け入れ条件

- 有効な Django Admin 管理ユーザーの正しい資格情報で login が `200` となり、session cookie が発行される。
- 誤パスワード、存在しない username、無効ユーザーの login 失敗は同一の `401` と一般化された本文となる。
- login は CSRF token がない場合または無効な場合に拒否される。匿名クライアントからも有効な CSRF token を付けた login は可能。
- `me` はログイン中ユーザーの `id`、`username`、期限を返し、資格情報や機密情報を返さない。
- login 成功から 43,199 秒後は `me` と保護 API を利用でき、43,200 秒経過時点およびそれ以後は拒否される。アクセスやセッション更新で期限が延長されない。
- logout 成功は `204`・空 body となり、同じ session cookie による以後の保護 API は拒否される。
- health と CSRF トークン取得以外の業務 API は認証を要求し、認証済み unsafe request には CSRF 検証を適用する。

## 運用上の注意

- アプリケーション経由のユーザー登録は提供しない。ユーザーは[以下の手順](#django-admin-でのユーザー管理)で Django Admin から作成する。
- `SESSION_COOKIE_HTTPONLY` は Django の既定値 `true`、`CSRF_COOKIE_HTTPONLY` は開発用設定の既定値 `false`。Cookie の `SameSite=Lax`、Domain（未指定）、Path（`/`）は Django の既定値を使用する。
- HTTPS 環境では `DJANGO_SESSION_COOKIE_SECURE=true` と `DJANGO_CSRF_COOKIE_SECURE=true` を設定する。開発 HTTP 環境の既定値は `false` であるため、本番環境へそのまま持ち込まない。
- 初回起動時にComposeが管理者ユーザーを自動作成する。現在の [docker-compose.yml](../../../docker-compose.yml) は `admin` / `password` を明示しており、`.env` で同じ変数を設定しても Compose の `environment` 値が優先される。この既知の開発用資格情報のまま外部公開しない。
- login 失敗のレート制限は実装していない。公開環境ではリバースプロキシ等を含む運用上の対策を別途検討する。

## Django Admin でのユーザー管理

1. リポジトリルートで Compose サービスを起動する。初回起動ではバックエンドがDBを待機し、標準 Django migration を適用してから管理者ユーザーを作成する。

   ```bash
   docker compose up --build -d
   docker compose ps
   ```

2. ブラウザーで `http://localhost:8000/admin/` を開く。現行 Compose の初期管理者は **ユーザー名 `admin`、パスワード `password`**。これはローカル演習専用の固定値である。起動後すぐに変更する。

   ```bash
   docker compose exec backend python manage.py changepassword admin
   ```

   初期管理者の自動作成は [`backend/entrypoint.sh`](../../../backend/entrypoint.sh) が行う。外部環境では Compose の固定値を使わず、強固な一意の秘密情報を Secret 等で注入し、初期ユーザーを安全に作成・変更する。

   自動作成を無効にした環境では、アプリケーションコンテナ起動後に管理者を作成する。

   ```bash
   docker compose exec backend python manage.py createsuperuser
   ```

3. Admin の「ユーザー」から「ユーザーを追加」を選び、username とパスワードを設定する。保存後、ユーザーを有効（`is_active`）にする。API ログインには有効ユーザーが必要だが、API 利用のために `is_staff` や superuser 権限を付与する必要はない。Admin に入れる管理者を追加する場合だけ、必要最小限のスタッフ権限を設定する。
4. 作成した username/password を使って [`POST /api/auth/login/`](#post-apiauthlogin) を呼び出す。アプリケーション側にユーザー登録 API はない。

## 環境設定・データベース migration

認証は Django 標準の `auth.User`、`django.contrib.auth`、`django.contrib.sessions` を利用する。カスタム User model、認証専用の新規テーブル、認証機能が追加する専用 migration はない。初期DBまたは未適用の標準 Django migration を適用する。

- 通常の Compose 起動では [`backend/entrypoint.sh`](../../../backend/entrypoint.sh) が `DJANGO_RUN_MIGRATIONS` 未指定時に `true` として `python manage.py migrate --noinput` を実行する。起動ログで適用結果を確認する。
- 起動時 migration を無効にしている環境、またはリリース運用で個別に適用する環境では、アプリのリリース前に次を実行する。アプリを複数台起動する場合、migration の同時実行を避けて単一の job/release step で行う。

  ```bash
  docker compose exec backend python manage.py showmigrations auth sessions
  docker compose exec backend python manage.py migrate
  ```

- `docs/setup.md` の手順に従い `.env.example` から `.env` を用意し、DB 接続値を環境に合わせる。HTTPS で公開する環境では、少なくとも次の Django 設定を実環境に合わせて設定する。`DJANGO_SECRET_KEY` は必ず Secret 管理し、例の値をそのまま使用しない。

  ```dotenv
  DJANGO_SECRET_KEY=<secret-managerから注入するランダムな秘密値>
  DJANGO_DEBUG=false
  DJANGO_ALLOWED_HOSTS=api.example.edu
  DJANGO_CSRF_TRUSTED_ORIGINS=https://app.example.edu
  DJANGO_SESSION_COOKIE_SECURE=true
  DJANGO_CSRF_COOKIE_SECURE=true
  ```

- `DJANGO_CSRF_TRUSTED_ORIGINS` はブラウザーから送られる実際の HTTPS origin（scheme を含む）に合わせる。フロントと API が別 origin の場合は CORS allowlist、Cookie の `SameSite` と domain、TLS 終端時の forwarded-proto 設定も併せて確認する。localhost の HTTP 開発では Secure を `false` のままとする。
- Compose は `DJANGO_CREATE_SUPERUSER=true` と初期管理者資格情報を固定値で設定している。`.env` だけではこの Compose 設定を置き換えられない。安全な初期ユーザー管理ができるよう Compose/deployment の注入方法を変更してから外部環境で起動し、弱い既定資格情報を残さない。

## CSRF トークン取得から API 呼び出しまで

ブラウザーでは Cookie を保持する同一 client/session を使い、次の順序で呼び出す。値は架空例であり、パスワードをソース管理やログへ保存しない。

1. `GET /api/csrf/` を実行し、`csrftoken` Cookie と JSON body の `csrftoken` を受け取る。
2. Cookie を送信し、body の token を `X-CSRFToken` に付けて `POST /api/auth/login/` を実行する。
3. Django はログイン成功時に CSRF token をローテーションする。ログイン後、同じ Cookie jar で `GET /api/csrf/` を再実行し、新しい token を取得する。
4. 保護 API の GET には session cookie、POST/PUT/PATCH/DELETE には session cookie と最新 `X-CSRFToken` を付ける。
5. 期限切れ後は保護 API が拒否されるので、新しい CSRF token を取得して login し直す。

ブラウザーの `fetch` 例は [CSRF API 仕様](csrf.md#利用例)、要求・応答の例は本書の[リクエスト例](#リクエスト例)を参照。

## 実装参照・根拠

- [Issue #22 の要件・受け入れ条件・実装計画](../../design-docs/backend-auth-api-issue-22.md)
- [API ルート定義](../../../backend/core/urls.py)
- [認証 View](../../../backend/core/auth_views.py)
- [セッション期限付き認証クラス](../../../backend/core/authentication.py)
- [認証権限](../../../backend/core/permissions.py)
- [公開 health/CSRF view と業務 API View](../../../backend/core/views.py)
- [Django URL 定義](../../../backend/lecture_system/urls.py)
- [Django 認証・session・CSRF middleware と Cookie 設定](../../../backend/lecture_system/settings.py)
- [バックエンドの初回 migration・管理者作成](../../../backend/entrypoint.sh)
- [Compose のサービス・初期管理者設定](../../../docker-compose.yml)
- [環境設定テンプレート](../../../.env.example)
- [開発環境起動手順](../../setup.md)
- [認証 API テスト](../../../backend/core/tests/test_auth_api.py)
- [現行 CSRF API 仕様](csrf.md)
- [現行 API 共通仕様](README.md)
