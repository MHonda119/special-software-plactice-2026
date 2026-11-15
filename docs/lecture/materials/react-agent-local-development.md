# ReAct Agent ローカル開発・動作確認

対象は `exercise/react-agent-backend-verification` の実装を含む作業ツリーです。資料用ブランチだけでは ReAct API / UI は動きません。既存の `POST /api/agents/{id}/execute/` を使い、新しい対話 Route は作りません。

## 1. 前提と確認範囲

- Docker Engine / Desktop と Docker Compose v2、インターネット接続。
- 既定ポートは frontend `3000`、backend `8000`、PostgreSQL `5432`。競合する場合は [共通セットアップ](../../setup.md) に従って変更します。
- ホストで Vite を使う場合は Node.js 20.19 以降、または 22.12 以降と npm。
- 実接続には講義配布の API キーと GPT-6 luna の利用権限が必要です。講師の指定した接続先が Responses API / function calling と本実装の設定を受け付けることを事前に確認します。
- 自動テストは LLM 応答をモックし、キーを使わずに検証します。UI テストの成功は、実モデルへの接続成功や料金の確認を意味しません。

リポジトリのルートで実行します。未コミットの作業を破棄したり、既存の `.env` を上書きしたりしないでください。

```bash
git branch --show-current
git status --short
docker compose version
```

本手順に必要な実装は [ReActAgentUsecase](../../../backend/core/react_usecases.py)、[ReActRunner](../../../backend/core/react_runner.py)、[Agent フォーム](../../../frontend/src/pages/AgentFormPage.jsx)、[チャット画面](../../../frontend/src/pages/ChatPage.jsx) です。

## 2. Compose で起動する

初回のみローカル設定を作成します。既存の設定は維持します。

```bash
if [[ ! -f .env ]]; then
  cp .env.example .env
fi
docker compose config --quiet
docker compose up --build -d db ollama backend frontend
docker compose ps
```

backend を再ビルドすることで `openai>=2,<3` を取り込みます。起動時に `0005_add_react_chat_usecase` を含む migration が適用され、未作成の場合のみ管理ユーザーが作成されます。既存 DB のデータは維持されます。

```bash
docker compose logs --tail=80 backend db
curl --fail http://localhost:8000/api/health/
docker compose exec backend python manage.py showmigrations core
docker compose exec backend python manage.py check
```

期待値は health の `{"status":"ok"}`、`core.0005_add_react_chat_usecase` の `[X]`、Django system check の成功です。起動直後に接続できない場合は backend の起動ログを確認します。ReAct は外部 OPENAI を使うため、Ollama のモデル取得や RAG 用データソースの登録を待つ必要はありません。Compose 自体は依存サービスとして Ollama を起動します。

| 用途 | URL |
| --- | --- |
| アプリ | http://localhost:3000/ |
| Django 管理画面 | http://localhost:8000/admin/ |
| 公開 health | http://localhost:8000/api/health/ |

## 3. GPT-6 luna を登録する

1. Django 管理画面にログインします。ローカル Compose の初期値はユーザー名 `admin`、パスワード `password` です。既存の環境で変更済みの場合はその資格情報を使います。
2. `Llms` の追加画面を開き、次の値を登録します。
3. 保存後、一覧に有効な GPT-6 luna が存在することを確認します。

| 項目 | 値 |
| --- | --- |
| Name | `GPT-6 luna` |
| Provider | `OPENAI` |
| Model | `gpt-6-luna` |
| Base url | `https://api.openai.com/v1`。講師指定の別 URL があればそちら |
| Api key | 配布された値を管理画面へ直接入力 |
| Extra | `{}` |
| Is active | 有効 |

base URL に `/responses` を付けません。モデル名の登録だけでは実際の利用権限・対応機能を検証しません。講義と違うモデルへ無断で置き換えず、接続不可なら講師にモデル名・接続先を確認します。

**キーはソース、手順書、Git、シェル履歴、スクリーンショットに残しません。** LLM の REST 書き込み応答にはキーが含まれるため、レスポンスを作業ログへ保存しないでください。外部 API の呼び出しには料金が発生する可能性があります。初期管理者パスワードはローカル演習以外で使わないでください。

## 4. UI から ReAct Agent を作成する

1. アプリのログイン画面でログインします。管理画面のログインとは別に API 用の認証が必要です。初期管理ユーザー、または管理画面で作成した有効ユーザーを使います。
2. `START` から機能メニューを開き、「エージェント」→「Agent作成」へ進みます。
3. 次の設定で保存します。

| 項目 | 設定例 |
| --- | --- |
| エージェント名 | `Stationery ReAct` |
| ユースケース | `ReActチャット` |
| LLM | `GPT-6 luna (OPENAI:gpt-6-luna)` |
| システムプロンプト | `文房具について日本語で簡潔に回答してください。` |
| モデル問い合わせ上限 (max_steps) | `8` |

ReAct では有効な OPENAI の LLM だけを選択できます。問い合わせ上限は1〜8の整数です。データソース・埋め込みモデル・temperature は指定しません。フォームは `config.max_steps` を保存します。API キーはチャット入力や Agent 設定へ入れません。

4. 一覧で `ReActチャット` と表示されることを確認します。
5. 一覧の実行ボタンを押し、チャットの `ReAct: 待機中` を確認します。

## 5. 二往復と状態表示を確認する

最初の質問:

```text
ノートを3冊買って1000円を支払うと、お釣りはいくらですか？
```

期待する観測:

- 送信後に `ReAct: 実行中` と進行表示が出ます。入力と送信ボタンは無効になり、二重送信できません。
- 応答後に `ReAct: 完了` となり、user / assistant のメッセージが並びます。
- 固定価格のノート250円×3冊なので、答えは **250円** です。生成文の表現は固定ではありません。
- URL が `/chat/会話UUID?...agentId=...&usecaseType=REACT_CHAT` に変わります。
- 回答の下に入力・出力トークン数が表示されます。これは対話内の全ステップの合計で、料金や実行中の進捗率ではありません。

続けて同じ画面で送信します。

```text
では、ペンを2本買って500円を支払うと、お釣りはいくらですか？
```

ペン120円×2本なので答えは **260円** です。URL の会話UUIDが変わらず、メッセージが4件になることを確認します。初回失敗は空の会話を作らず、成功後に会話と user / assistant を一括保存します。

ブラウザを再読込し、4件の履歴と回答ごとの usage が戻ることを確認します。また「メニューへ戻る」→「シンプルチャット」のセッション一覧から同じ会話を開くと、所属Agentを取得して ReAct として再開します。Agentを無効化すると再開時の取得が404になります。

必要なら DevTools の Network で、最初も継続時も `/api/agents/ID/execute/` を使い、2回目のJSONに同じ `session_uuid` があることを確認します。`/api/sessions/UUID/chat/` はReAct用ではありません。読み取りAPIの `agent` は所属ID、メッセージの `usage` は保存済み利用量です。所属はセッションCRUDから書き換えられません。

**UI が表示するのは待機・実行中・完了・失敗・履歴読込中です。** 現行APIはストリーミングせず、ツール実行の途中段階、Thought、SDKの内部履歴を返しません。「実行中」を特定のツールの進捗と解釈しないでください。タイムアウトは通信ごとに30秒、SDKの自動再試行は0回、リクエスト全体の期限は未実装です。

## 6. フロントをホストの Vite で開発する場合

Compose の代わりにフロントだけホストで動かす方法です。backend / DB は Compose を使います。ポート3174を使い、Compose版3000と同時起動しても競合しません。

`.env` の `DJANGO_CSRF_TRUSTED_ORIGINS` にホスト側のOriginも含めます。既存の必要なOriginは削除しません。

```dotenv
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:3174,http://127.0.0.1:3174
```

```bash
docker compose up --build -d db ollama backend
npm --prefix frontend install
VITE_PROXY_TARGET=http://127.0.0.1:8000 npm --prefix frontend run dev -- --host 127.0.0.1 --port 3174 --strictPort
```

http://127.0.0.1:3174/ を開きます。backend の公開ポートを8001等へ変えた場合は `VITE_PROXY_TARGET` も変更します。`VITE_PROXY_TARGET` の既定値はCompose内向け `http://backend:8000` なので、ホスト起動時は明示してください。これは Vite の `/api` プロキシ設定であり、外部 LLM の base URL とは別です。

Originを変更した際はbackendを再作成して設定を取り込み、アプリへログインし直します。Remote SSH で開発する場合は3174と8000をローカルへ転送し、実際にブラウザで使うOriginを設定します。

## 7. 自動検証

### backend と静的検査

```bash
bash scripts/test-backend.sh
bash scripts/lint-backend.sh
bash scripts/lint-frontend.sh
```

これらは一時コンテナを使います。backendテストはSQLiteのメモリDBで migration を適用し、外部 LLM はモックします。frontendのlintは型チェックとESLintを実行します。

ホスト側のビルド・単体テスト:

```bash
npm --prefix frontend run test:unit
npm --prefix frontend run build
```

既存 `dist` がコンテナで作成され、権限エラーになる場合は所有権を変更・削除せず、一時出力先でも確認できます。

```bash
npm --prefix frontend run build -- --outDir /tmp/react-agent-frontend-build --emptyOutDir
```

### ReAct UI のブラウザテスト

ホストで上記のViteが起動済み、Chromeがインストール済みの場合:

```bash
npm --prefix e2e install
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3174 npm --prefix e2e test -- tests/react-agent.spec.ts --project=chrome --output=/tmp/react-agent-e2e-results
```

Chromeがなければ `e2e` ディレクトリで `npx playwright install chrome` を実行するか、以下のコンテナ方式を使います。

Compose版frontendを起動した場合:

```bash
docker compose --profile e2e build e2e
docker compose --profile e2e run --rm --no-deps e2e npm test -- tests/react-agent.spec.ts --project=chrome --reporter=line --output=/tmp/react-agent-e2e-results
```

[UIテスト](../../../e2e/tests/react-agent.spec.ts) は設定の作成・編集、OPENAI制約、max_steps、待機と実行中、二重送信防止、同じ会話の継続・再開、再読込後のusage、422 / 502 / 504での入力復元・再試行、360px幅と2,000文字上限を検証します。実APIキーは使いません。

### 検証済みの結果 (2026-11-15)

| 対象 | 結果 |
| --- | --- |
| backend 全体 | 83テスト成功。テストSQLiteでmigration適用 |
| frontend 単体 | 14テスト成功 |
| ブラウザ | ReAct 6ケース + 認証28ケース、合計34件成功 |
| 静的検査 | backend Ruff、frontend TypeScript / ESLint成功 |
| 本番ビルド | 一時出力先で成功。500kB超のバンドル警告は残る |
| 画面 | 1280px / 360pxで表示確認。モバイルの横はみ出しなし |

ブラウザ検証はホストのViteとモックAPIで行っています。Composeの実サービス起動、実DBのLLM登録、新migrationのPostgreSQL適用、実モデルの応答・課金は今回の検証対象外です。実環境での確認は手順2〜5を実施してください。

## 8. エラーの切り分け

| 観測 | 確認すること |
| --- | --- |
| ReActの選択肢がない | 実装を含む検証作業ツリーか。古いfrontendを表示していないか |
| LLM一覧が空 | 管理画面で登録したか。Is activeが有効か。APIログイン済みか |
| 保存ボタンが無効 | 名前、OPENAIのLLM、max_stepsの整数1〜8 |
| 400 | 空入力、2,000文字超過、UUID・options・max_steps等の入力不正 |
| 401 / ログインへ戻る | API認証期限切れ。アプリへ再ログイン。管理画面ログインだけでは不十分 |
| 403 / CSRFエラー | ブラウザのOriginとDJANGO_CSRF_TRUSTED_ORIGINS。変更をbackendへ取り込んだか |
| 404 | Agentまたは会話が無効・不存在。別Agentの会話UUIDを渡していないか |
| 422 | キー・モデル・provider・有効状態・既定max_steps。会話のLLMとAgentのLLMが一致するか |
| 502 | 上流APIの失敗、モデル未完了・拒否・空回答、問い合わせ上限到達。利用権限・モデル名・API対応を確認 |
| 504 | SDKの通信タイムアウト。接続先とネットワークを確認 |
| サーバー接続不可 | health、backendログ、公開ポート、VITE_PROXY_TARGET |

ReActの捕捉された失敗では仮のuserメッセージをUIから外し、入力欄へ戻します。成功した履歴は維持します。自動再送はしません。ネットワーク断ではサーバー側の成功有無が分からないこともあるため、履歴を確認してから再送してください。冪等キー・同時送信の直列化・ユーザー別所有権は未実装です。

max_stepsを1にすると、ツール呼び出しが必要な質問は上限に到達しやすくなりますが、実モデルの挙動で変わります。失敗表示の確実な再現には上記のモックE2Eを使い、不正キー等で無駄な有料リクエストを増やさないでください。

## 9. 停止と参照

ホストのViteは実行ターミナルで `Ctrl+C`。Composeは次で停止します。

```bash
docker compose down
```

`--volumes` は付けません。PostgreSQLの登録データを失うためです。一般的な運用上の注意は [セットアップ](../../setup.md)、API契約は [Agent API](../../backend/api/agents.md) と [Session API](../../backend/api/sessions.md)、実装は [バックエンド実装資料](react-agent-backend-implementation.md) を参照してください。
