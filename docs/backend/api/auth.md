# 認証 API

Issue #17 に対応した現行実装の仕様。Django 標準ユーザーと固定 12 時間のセッション認証を提供する。

## 契約

- UserModel は Django 標準の `auth.User`。一意の `username` とハッシュ化されたパスワードを使用し、Django Admin で管理する。登録 API は作らない。
- 認証方式は Django のサーバー側セッションのみ。Basic 認証や独自トークンでは認証しない。
- 業務 API と `/api/` は全操作で認証必須。所有者によるデータ分離は行わない。
- 匿名アクセスの例外は `GET /api/health/`、`GET /api/csrf/`、`POST /api/auth/login/`。ヘルスチェックは生存確認のみ。
- 更新系はログインを含め CSRF 検証する。CSRF API の Cookie と応答トークンを取得し、`X-CSRFToken` で送る。ログイン時にトークンが回転するため取得し直す。
- セッション Cookie は HttpOnly、SameSite=Lax。HTTPS 運用では Secure を有効化する。認証応答は `Cache-Control: no-store`。

## エンドポイント

| メソッド | URL | 入力 | 成功 |
| --- | --- | --- | --- |
| POST | `/api/auth/login/` | JSON の `username`、`password`（必須の空でない文字列） | 200、ユーザーと期限 |
| GET | `/api/auth/me/` | ボディなし | 200、ユーザーと期限 |
| POST | `/api/auth/logout/` | ボディ不要、認証必須 | 204、ボディなし |

`username` は最大 150 文字で前後空白を除去する。`password` の空白は保持する。
ログインのリクエスト例。`Content-Type: application/json` と CSRF トークン、対応する Cookie を送る。

```json
{
  "username": "student",
  "password": "example-password"
}
```

ログイン・me の成功応答は次の形式。日時は UTC の ISO 8601。パスワードとハッシュは返さない。

```json
{
  "user": {"id": 1, "username": "student"},
  "expires_at": "2026-10-26T12:00:00+00:00"
}
```

## 固定期限・副作用

- ログイン成功時刻 + 43,200 秒をセッションに保存し、Django セッション自体の有効期限も同じ日時にする。
- 現在時刻が期限未満なら有効、期限以上なら失効。通信・画面更新・me 取得では延長しない。
- 保護対象 API は毎回期限を検証し、期限切れ・期限情報なしの認証セッションをサーバー側で無効化する。
- ログインは Django の標準処理でセッションキーを更新し、ログアウトはセッションを削除する。削除済みキーの再送でも利用できない。
- フロントエンドは再読み込み時に me を確認し、期限タイマー、復帰・フォーカス時にも期限を確認する。認証失敗時に mock データへ切り替えない。

## エラー

| ステータス | 条件 | 形式 |
| --- | --- | --- |
| 400 | 入力不足・空文字・不正な型 | 項目名をキーにしたエラー配列 |
| 401 | ユーザー不存在・パスワード不正・無効ユーザー | 共通の `detail`、存在有無を区別しない |
| 401 | 未認証・ログアウト済み・期限切れ | `detail` |
| 403 | CSRF 不正・権限不足 | `detail`。401 と区別する |

通信障害・403 は認証切れと混同せず、画面に失敗を表示する。

## 検証条件・互換性

- Admin 作成ユーザーのログイン、無効ユーザー拒否、パスワード非公開を確認する。
- 時刻を制御して期限直前・期限到達・継続操作後の固定期限・古い Cookie の再送を確認する。
- 全業務ルートの匿名拒否と公開例外、ログインを含む CSRF 拒否を確認する。
- UI のログイン・手動ログアウト・表示中の期限切れ・再読み込み・復帰を確認する。
- 既存の匿名 API クライアントはログインと CSRF 対応が必要。既存ユーザーデータの移行は対象外。

## 参照

- [API 共通仕様](README.md)
- [Admin でのユーザー登録・環境設定](../../setup.md)
- [認証と固定期限の検証](../../../backend/core/authentication.py)
- [認証 API の処理](../../../backend/core/auth_views.py)
- [ログイン入力検証](../../../backend/core/auth_serializers.py)
- [認証テスト](../../../backend/core/tests/test_auth_api.py)
- [設定](../../../backend/lecture_system/settings.py)
- [ルート](../../../backend/core/urls.py)
- [Issue #17](https://github.com/MHonda119/special-software-plactice-2026/issues/17)
