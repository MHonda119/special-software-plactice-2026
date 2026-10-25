# CSRF API

## エンドポイント

| メソッド | パス | 概要 |
| --- | --- | --- |
| GET | `/api/csrf/` | CSRFトークンを取得し、CSRF Cookieを発行・更新する |

## リクエスト

パスパラメータ、クエリパラメータ、リクエストボディは不要。Cookieを保持できるクライアントで実行する。

```bash
curl -c cookies.txt http://localhost:8000/api/csrf/
```

## レスポンス

成功時は `200 OK`。`csrftoken` Cookieの発行・更新はDjangoのCSRFミドルウェアが行う。

```json
{
  "csrftoken": "<masked-csrf-token>"
}
```

| フィールド | 型 | 説明 |
| --- | --- | --- |
| csrftoken | string | `django.middleware.csrf.get_token` が返すマスク済みトークン |

レスポンスボディのトークンとCookieの値は、文字列として一致するとは限らない。ボディのトークン、またはCookieの値を `X-CSRFToken` ヘッダーに設定できる。対応するCookieも送信する。

## 利用例

ブラウザでログイン済みDjangoセッションを使って更新する場合の例。

```javascript
const csrfResponse = await fetch('/api/csrf/', {
  credentials: 'include',
  headers: { Accept: 'application/json' },
});
const { csrftoken } = await csrfResponse.json();

const response = await fetch('/api/sessions/', {
  method: 'POST',
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrftoken,
  },
  body: JSON.stringify({ llm: 1, title: 'New Session' }),
});
```

## 挙動・制約

- このAPIはログインやアクセストークンの発行を行わない。
- セッション認証時のPOST/PUT/PATCH/DELETEでCSRF検証に失敗すると `403`。匿名アクセスに一律でCSRFを要求するものではない。詳細は [共通仕様](README.md) を参照。
- 開発時の既定値では `CSRF_COOKIE_HTTPONLY=false`、`CSRF_COOKIE_SECURE=false`。環境変数 `DJANGO_CSRF_COOKIE_HTTPONLY`、`DJANGO_CSRF_COOKIE_SECURE` で変更できる。
- オリジンの検証には `DJANGO_CSRF_TRUSTED_ORIGINS` の設定も関係する。Cookie・ヘッダーが存在するだけで、すべてのオリジンが許可されるわけではない。
- 未対応のHTTPメソッドは `405 Method Not Allowed`。

## 実装参照

- [csrf_tokenとget_tokenの呼び出し](../../../backend/core/views.py)
- [ルート定義](../../../backend/core/urls.py)
- [Cookie・CSRF設定](../../../backend/lecture_system/settings.py)
- [フロントエンドのCSRF利用例](../../../frontend/src/services/apiClient.js)
