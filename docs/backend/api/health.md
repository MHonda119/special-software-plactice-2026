# ヘルスチェックAPI

## エンドポイント

| メソッド | パス | 概要 |
| --- | --- | --- |
| GET | `/api/health/` | バックエンドがHTTPリクエストに応答できることを確認する |

## リクエスト

パスパラメータ、クエリパラメータ、リクエストボディは不要。

```bash
curl http://localhost:8000/api/health/
```

## レスポンス

成功時は `200 OK`。

```json
{
  "status": "ok"
}
```

| フィールド | 型 | 説明 |
| --- | --- | --- |
| status | string | 固定値 `ok` |

## 挙動・制約

- データベース、Ollama、外部LLM、Chromaの稼働状態は検査しない。
- 外部サービスが停止していても、このハンドラーが実行できれば `200` を返す。依存サービスを含めたreadinessチェックではない。
- 未対応のHTTPメソッドでは `405 Method Not Allowed` を返す。共通の認証・エラー仕様は [README.md](README.md) を参照。

## 実装参照

- [ルート定義](../../../backend/core/urls.py)
- [health](../../../backend/core/views.py)
