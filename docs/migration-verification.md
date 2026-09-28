# 2025年度版からの移植・検証結果

検証日: 2026-09-28

## 移植範囲

移植元は同じ階層の `special-software-plactice-2025`、コミットは `81f3e14ccf48116e475a7108743caf3e93c4dc2d` です。移植元には変更を加えていません。

Git管理対象の118ファイルのうち114ファイルを移植し、React画面、Django API・マイグレーション・テスト、API資料、Docker Compose、Kubernetes教材、CI、演習スクリプト、画像比較用の基準画像、ライセンスを引き継ぎました。

次の4ファイルはそのままコピーしていません。

- 旧 `README.md`: 2026年度の講義説明・日程を保持し、アプリ構成と起動手順を追記しました。
- `scripts/api_basics/.env copy`: キーを含めない `.env.example` に置き換えました。
- `e2e/test-results/` 配下の旧実行結果2ファイル: 検証時に生成する成果物として除外しました。

`.git`、個別環境の `.env`、仮想環境、`node_modules`、キャッシュ、ローカル作業ファイル、既存のDB・モデルデータは移植対象に含めていません。

## 検証に伴う修正

- Composeのホスト公開ポートを `POSTGRES_HOST_PORT`、`BACKEND_PORT`、`FRONTEND_PORT` で変更できるようにしました。既定値は従来どおりです。
- バックエンドのtest/lintとフロントエンドのlintを、依存サービスや公開ポートが不要な一時コンテナで実行する方式へ変更しました。
- バックエンドlintで `/bin/sh` が扱えない `pipefail` を除去しました。
- フロントエンドlintは匿名ボリュームへ `npm ci` し、起動中のアプリと依存ファイルを変更する競合を解消しました。検証中に発生した依存ファイル欠落は再インストールで復旧し、その後のE2Eは成功しています。
- E2EのTypeScript設定を `NodeNext` に統一し、Node.jsの型定義を追加しました。
- backend/frontendの `.dockerignore`、環境ファイル・E2E生成物のGit除外設定を追加しました。
- CIでE2Eの失敗を無視する設定を削除し、手順の参照先を2026年度版へ更新しました。

アプリの画面・API・モデル・マイグレーションとE2Eの画像比較基準は移植元のままです。

## 検証結果

| 対象 | 実行した検証 | 結果 |
| --- | --- | --- |
| backendイメージ | `docker compose build backend` | 成功 |
| frontend・Ollama・E2Eイメージ | `docker compose build frontend ollama e2e` | 成功。frontendはCompose指定のdevステージ |
| Compose | `docker compose config --quiet`、4サービス起動 | 成功 |
| バックエンド | `bash scripts/test-backend.sh` | 37件成功 |
| バックエンドlint | `bash scripts/lint-backend.sh` | Ruff成功 |
| Django設定 | `manage.py check`（SQLiteテスト設定） | 問題0件 |
| マイグレーション整合性 | `manage.py makemigrations --check --dry-run`（SQLiteテスト設定） | 差分なし |
| 新規DB初期化 | 起動時にPostgreSQLへマイグレーション、静的ファイル収集、管理ユーザー作成 | 成功 |
| フロントエンド | `npm ci`、`npm run typecheck`、`npm run lint`、`npm run build` | 成功 |
| フロントエンドDocker検証 | `bash scripts/lint-frontend.sh` | 成功 |
| E2E型チェック | `cd e2e && npx tsc --noEmit` | 成功 |
| ブラウザE2E | `docker compose --profile e2e run --rm --no-deps -T e2e npm run test:ci` | 1件成功。スタート画面→メニュー画面、既存画像との比較 |
| Kubernetes教材 | `kubectl kustomize` で `manifests/base`、`manifests/overlays/dev`、`manifests/overlays/stage` を展開 | すべて成功 |
| 演習・補助スクリプト | `python3 -m compileall -q scripts/api_basics`、シェル構文チェック | 成功 |

ホストのNode.jsは22.18.0、npmは10.9.3です。新規ビルドしたbackendはPython 3.12、Django 5.2.17、Django REST Framework 3.18.1、ChromaDB 1.5.9で検証しました。

### 実サービスによる結合確認

既存アプリとのポート競合を避け、frontendを13000、backendを18000、PostgreSQLを15432で起動しました。HTTP API経由で一時レコードを作成し、次を確認しました。

1. backendへの直接接続とfrontendの `/api/` プロキシ経由のヘルスチェック。
2. `gemma3:270m` をLLMとして登録し、セッション作成、実モデルからの応答、PostgreSQLに保存したuser/assistant履歴の取得。
3. `BASIC_CHAT` エージェントの実行、同一セッションでの追加会話、systemメッセージが1件に保たれること。
4. `nomic-embed-text` による実埋め込み生成、データソース・チャンクの作成、ChromaDBからの一覧取得。
5. `RAG_CHAT` による検索と実モデル応答、登録したチャンクを指す引用、`used_chunks=1` の取得。
6. チャンク削除後の一覧が空になること。

結合確認用のセッション・エージェント・データソース・LLMレコードは確認後に削除しました。ブラウザテストのHTMLレポートは、ローカルの `e2e/playwright-report/index.html` に保存しています（Git管理対象外）。

検証用の2026年度版コンテナと今回作成したボリュームは終了後に削除しました。既存の別アプリは停止していません。ローカルの `.env` は公開テンプレートから作成し、上記の検証用ポートとCSRFの許可オリジンを設定して残しています。`docker compose up -d` で再起動できます（モデルは再ダウンロードされます）。

## 検証の範囲と既存の制約

- Viteのビルドは成功していますが、既存の約595 kBのJavaScriptバンドルにサイズ警告があります。
- OpenAI/Geminiなど外部の有料APIと演習スクリプトのAPI実呼び出しは行っていません。バックエンド単体テストでは外部通信をモックしています。
- Kubernetesはマニフェスト展開までの確認で、クラスタへのデプロイは行っていません。
- ブラウザE2Eの自動化対象は画面遷移・画像比較の1件です。チャットとRAGの結合確認はHTTP API経由です。
- Chromaの保存先には元のComposeと同様にボリューム設定がありません。コンテナ再作成時の扱いは [起動・検証ガイド](setup.md) を参照してください。

再実行の手順は [起動・検証ガイド](setup.md) にまとめています。
