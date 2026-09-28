# special-software-plactice-2026 起動・検証ガイド

この教材は、Reactの画面、DjangoのAPI、PostgreSQL、OllamaをDocker Composeで起動します。RAG用のChromaDBはバックエンド内で利用します。

## 前提

- Docker EngineまたはDocker Desktopと、`docker compose` コマンド
- イメージ・パッケージ・LLMモデルのダウンロードに利用するインターネット接続
- ホスト側の空きポート `3000`、`8000`、`5432`

以降は `special-software-plactice-2026` のルートで実行します。2025年度のアプリを同時起動している場合は、`.env` で2026年度側の公開ポートを変更できます。

## 初回起動

初回のみ、公開用テンプレートからローカル設定ファイルを作成します。

```bash
cp .env.example .env
```

`.env.example` はローカル開発用の設定例です。必要に応じて `.env` 内のデータベース設定や `DJANGO_SECRET_KEY` を変更してください。既存の `.env` がある場合は上書きせず利用します。

2025年度のアプリと同時起動する場合の `.env` 設定例です。`FRONTEND_PORT` を変える場合は、ブラウザからのPOSTなどを許可するため `DJANGO_CSRF_TRUSTED_ORIGINS` も合わせて指定します。以降のアクセスURLも設定したポートに読み替えてください。

```dotenv
POSTGRES_HOST_PORT=5433
BACKEND_PORT=8001
FRONTEND_PORT=3001
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:3001,http://127.0.0.1:3001
```

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker compose logs -f backend ollama
```

バックエンドはデータベースへの接続を待って、マイグレーション、静的ファイル収集、初回の管理ユーザー作成を行います。Ollamaは `gemma3:270m` を取得します。モデルの準備が完了するまでチャットは利用できません。

ログ表示は `Ctrl+C` で終了できます。次のコマンドでAPIの応答とモデルの取得を確認します。

```bash
curl --fail http://localhost:8000/api/health/
docker compose exec ollama ollama list
```

フロントエンドは http://localhost:3000 、管理画面は http://localhost:8000/admin/ です。APIのみ起動を確認したい場合は http://localhost:8000/api/ を開けます。

## チャットを使う

1. Django管理画面へログインします。Composeの既定値はユーザー名 `admin`、パスワード `password` です。
2. `Llms` からLLMを追加します。

   | 項目 | 設定例 |
   | --- | --- |
   | Name | `Local Gemma` |
   | Provider | `Ollama` |
   | Base url | `http://ollama:11434`（空欄でも既定値を使用） |
   | Model | `gemma3:270m` |
   | Api key | 空欄 |
   | Extra | `{}` |
   | Is active | 有効 |

3. フロントエンドの `START` →「シンプルチャット」で登録したモデルを選択します。
4. 「新しいセッションを開始」からメッセージを送信し、応答と履歴を確認します。

管理ユーザーは未作成の場合のみ自動作成されます。作成後のパスワード変更には次を使用できます。

```bash
docker compose exec backend python manage.py changepassword admin
```

このCompose構成はローカル演習向けです。外部公開には認証・アクセス制御や各環境の設定が必要です。

## RAGを使う場合

チャット用モデルとは別に、埋め込みを生成できるモデルが必要です。初期取得される `gemma3:270m` はチャット用です。Ollamaで埋め込みモデルを追加する例は次のとおりです。

```bash
docker compose exec ollama ollama pull nomic-embed-text
```

管理画面で `provider=OLLAMA`、`model=nomic-embed-text` のLLMを登録し、「データソース管理」でそのLLMを選んでデータソースとテキストチャンクを作成します。次に「エージェント」で `RAG_CHAT`、チャット用LLM、対象データソース、埋め込みモデルを設定して会話を開始します。データソース登録時と検索時の埋め込みモデルは一致させてください。

詳細な項目やリクエスト例は [Datasource API](../backend/documents/datasource_api.md) と [Agent API](../backend/documents/agent_api.md) を参照してください。これらには将来の設計案も含まれます。

## 検証

以下のコマンドで静的検証、バックエンドテスト、ブラウザテストを実行できます。

### Docker環境でのチェック

アプリを起動した状態で実行します。

```bash
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
bash scripts/test-backend.sh
bash scripts/lint-backend.sh
bash scripts/lint-frontend.sh
docker compose exec frontend npm run build
```

バックエンドテストは `lecture_system.test_settings` を使い、SQLiteのメモリ内データベースで `core` のテストを実行します。LLM・埋め込み等の外部サービス呼び出しはモックを利用します。フロントエンドのlintスクリプトはTypeScriptによるチェックとESLintを実行します。

`test-backend.sh`、`lint-backend.sh`、`lint-frontend.sh` は一時コンテナで実行するため、これらのスクリプトだけならDBやOllamaを起動する必要はありません。

### ブラウザのE2Eテスト

```bash
docker compose --profile e2e build e2e
bash scripts/test-e2e.sh
```

E2Eサービスは専用の `e2e` プロファイルで実行します。テストスクリプトは必要なアプリのサービスを起動します。現行のテストはスタート画面から機能メニューへの遷移とスクリーンショットの比較を確認します。LLMが応答することは、前述のチャット操作で別途確認してください。

詳細は [E2Eガイド](../e2e/README.md) を参照してください。

### Dockerを使わない静的検証・バックエンドテスト

ホストにPython 3.12とNode.js 20.19以降（または22.12以降）、npmを用意すれば、アプリのコンテナを起動せずに以下のチェックを実行できます。

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cd backend
DJANGO_SETTINGS_MODULE=lecture_system.test_settings python manage.py check
DJANGO_SETTINGS_MODULE=lecture_system.test_settings python manage.py makemigrations --check --dry-run
DJANGO_SETTINGS_MODULE=lecture_system.test_settings python manage.py test core
ruff check .
cd ../frontend
npm ci
npm run typecheck
npm run lint
npm run build
cd ..
```

この方法ではPostgreSQL、Ollama、DockerイメージやComposeの起動動作は検証できません。

## 停止と再起動

```bash
docker compose down
docker compose up -d
```

PostgreSQLのデータとOllamaのモデルは名前付きボリュームに保存されます。`docker compose down --volumes` はこれらのデータも削除するため、初期化する場合のみ使用してください。

ChromaDBの保存先はバックエンドコンテナ内の `/data/chroma`（`CHROMA_PERSIST_DIR` で変更可能）です。現行のComposeにはこの保存先のボリューム設定がないため、`docker compose down` やコンテナ再作成でRAGのチャンクが失われます。継続利用する場合は保存先をボリュームへ割り当ててください。

## 起動できない場合

- ポートが使用中の場合: `.env` の `POSTGRES_HOST_PORT`、`BACKEND_PORT`、`FRONTEND_PORT` を空いているポートに変更します。
- モデルが見つからない場合: `docker compose logs ollama` と `docker compose exec ollama ollama list` でダウンロード状況とモデル名を確認します。
- APIへ接続できない場合: `docker compose logs backend db` でDB接続とマイグレーションの完了を確認します。
- モデル一覧が空の場合: 管理画面でLLMを登録し、`Is active` が有効になっていることを確認します。
- 既存DBの認証で失敗する場合: `.env` のデータベース設定と、ボリューム初回作成時の設定が一致しているか確認します。`.env` の変更だけでは既存DBのユーザーやパスワードは更新されません。
