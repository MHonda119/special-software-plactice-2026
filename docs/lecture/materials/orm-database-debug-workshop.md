# バックエンド演習: ORM・データベース・テスト・デバッグ

## 1. この講義の目的

この講義では、本リポジトリの Django / Django REST Framework バックエンドを題材に、HTTP リクエストがモデル操作やデータベースへの SQL 実行につながる過程を追跡します。対象は、前回作成した Auth API と、会話を管理する Session API です。


### 到達目標

- URL、View、Serializer、Usecase、Model の役割と呼び出し順を説明できる
- 認証用のセッションと会話用のセッションを区別できる
- ORM の取得・作成・更新・削除が、いつ SQL を実行するか説明できる
- Logger を使い、秘密情報を出力せずに処理経路と失敗箇所を調べられる
- VS Code のデバッグモードでテストを実行し、ブレークポイントで変数とモデルを観察できる
- テスト用データベース、モック、トランザクションを区別し、検証できた範囲を説明できる

### 進め方と提出物

各演習では、実行前の予想、停止した関数、観察した値、発行された SQL の種類、結論を Markdown に記録してください。スクリーンショットにも、パスワード、Cookie、トークン、会話本文などが写らないよう注意します。

演習用の変更は、手元の作業用ブランチで行ってください。デバッグ用の設定を共有環境や本番環境に反映させず、演習後の片付けでも既存の未コミット変更を消さないようにします。


## 2. 最初に区別する「2 種類のセッション」

| 対象 | 主な入口 | 意味 | 観察するモデル・値 |
| --- | --- | --- | --- |
| 認証セッション | Auth API の `login`、`me`、`logout` | ブラウザからのリクエストをログイン済みユーザーと結び付ける仕組み | Django の `Session`、`request.user`、`request.session` |
| 会話セッション | Session API の作成、メッセージ一覧、チャット | 使用する LLM と会話履歴を管理する単位 | アプリケーションの `ChatSession` と `Message` |

ログインしただけで `ChatSession` が作成されるわけではなく、会話の UUID も認証 Cookie の代わりにはなりません。また、認証に成功することと、特定の会話を操作する権限があることは、分けて考える必要があります。

### コードの案内

| 役割 | ファイル |
| --- | --- |
| 認証入力の検証 | [auth_serializers.py](../../../backend/core/auth_serializers.py) |
| ログイン・ログアウト・ユーザー情報の応答 | [auth_views.py](../../../backend/core/auth_views.py) |
| 認証セッションの期限確認 | [authentication.py](../../../backend/core/authentication.py) |
| 会話 API の入口 | [views.py](../../../backend/core/views.py) |
| 会話の保存と LLM 呼び出し | [usecases.py](../../../backend/core/usecases.py) |
| 会話とメッセージのモデル定義 | [models.py](../../../backend/core/models.py) |
| 認証 API のテスト | [test_auth_api.py](../../../backend/core/tests/test_auth_api.py) |
| 会話保存のテスト | [test_chat_usecase.py](../../../backend/core/tests/test_chat_usecase.py) |
| API の URL 登録 | [core/urls.py](../../../backend/core/urls.py) |
| 入力とモデルを結び付ける Serializer | [serializers.py](../../../backend/core/serializers.py) |

`core/urls.py` の Router は、Session API の標準的な作成・取得・削除の URL を生成します。プロジェクト側の [urls.py](../../../backend/lecture_system/urls.py) が、その入口に `/api/` を付けます。

| 関係 | コード上の定義 | 観察すること |
| --- | --- | --- |
| `ChatSession` → `LLM` | `ForeignKey(..., on_delete=PROTECT)` | `llm_id` は外部キーの値、`llm` は関連モデルへの参照 |
| `ChatSession` → `Agent` | `ForeignKey(..., null=True, on_delete=SET_NULL)` | Agent がなくても会話を保持できる設計 |
| `Message` → `ChatSession` | `ForeignKey(..., related_name="messages", on_delete=CASCADE)` | 逆方向の取得には `session.messages` を使用 |

現在の `ChatSession` にはユーザーの外部キーがなく、View の QuerySet もユーザー単位では絞り込まれていません。この講義では、ユーザー別の会話所有権が実装済みであるとは扱いません。

## 3. 準備：テストと VS Code の実行環境

### 3-1. 使用するデータベースの確認

| 実行方法 | 設定 | データベース |
| --- | --- | --- |
| Compose による通常起動 | [settings.py](../../../backend/lecture_system/settings.py) | PostgreSQL（接続情報は環境変数から取得） |
| 標準テストスクリプト | [test_settings.py](../../../backend/lecture_system/test_settings.py) | インメモリ SQLite |
| 本資料のデバッグ設定 | 上記のテスト設定を明示 | インメモリ SQLite |

SQLite のテストでも ORM は実際の SQL を実行します。モックに置き換えるのは外部 LLM の呼び出しであり、データベース全体ではありません。テストのレコードは、通常起動した PostgreSQL を管理画面や DB ツールで開いても見えません。

### 3-2. 既存テストの通常実行

次のコマンドは、リポジトリルートで実行してください。事前に Docker、Docker Compose、Compose が読み込む環境変数ファイル、backend イメージを用意します。初回のセットアップは [setup.md](../../setup.md) を参照してください。イメージがなければ `docker compose build backend` を実行します。

```bash
bash scripts/test-backend.sh core.tests.test_auth_api
bash scripts/test-backend.sh core.tests.test_chat_usecase.ChatUsecaseTests.test_run_creates_assistant_message
```

[test-backend.sh](../../../scripts/test-backend.sh) は、一時 backend コンテナを `--rm --no-deps` で実行します。PostgreSQL、Ollama、開発サーバーを起動する必要はありません。引数なしの場合は `core` 全体を実行します。

スクリプトはテストラベルを受け取りますが、先頭に任意の Django オプションを付ける使い方には対応していません。`--verbosity` などを使用する場合は、次のローカル実行で `manage.py test` に直接渡します。

### 3-3. VS Code で使用する Python の準備

基本的には、VS Code で開いている Linux 環境の Python からテストを起動します。依存関係がコンテナ内にしかない場合は、後述の Docker attach を利用してください。

backend の [Dockerfile](../../../backend/Dockerfile) と合わせ、Python 3.12 の仮想環境を準備します。次のコマンドはリポジトリルートで実行します。

```bash
python3.12 -m venv ~/.venvs/lecture-backend
source ~/.venvs/lecture-backend/bin/activate
python -m pip install -r backend/requirements.txt
python backend/manage.py test core.tests.test_auth_api --settings lecture_system.test_settings --verbosity 2
```

Python 3.12 がない場合や依存関係を導入できない場合は、3-4 の Dev Containers を使う手順へ進んでください。SQLite を使う場合でも、Django が読み込むアプリケーションの依存関係は必要です。[requirements.txt](../../../backend/requirements.txt) の一部を省いてインストールしないよう注意してください。

VS Code では Python 拡張機能と Python Debugger 拡張機能を有効にします。`Python: Select Interpreter` で、上記の仮想環境の Python を選択します。Remote SSH を使う場合は、リモート側の拡張機能とインタープリターを確認します。

ターミナルの `python` と、VS Code の選択中インタープリターが一致するとは限りません。デバッグコンソールで `__import__("sys").executable` を評価し、実際に使われている Python を確認します。

### 3-4. テスト起動用のデバッグ設定

#### ローカル起動の設定

VS Code の「実行とデバッグ」から設定ファイルを作成します。リポジトリルートを開いていることを確認したうえで、次の内容を `.vscode/launch.json` に追加してください。すでに設定がある場合は、ファイル全体を上書きせず、`configurations` に項目を追加します。

```json
{
	"version": "0.2.0",
	"configurations": [
		{
			"name": "Lecture: Auth login test",
			"type": "debugpy",
			"request": "launch",
			"program": "${workspaceFolder}/backend/manage.py",
			"cwd": "${workspaceFolder}/backend",
			"args": [
				"test",
				"core.tests.test_auth_api.AuthApiTests.test_login_and_me_only_expose_user_and_expiry",
				"--verbosity",
				"2"
			],
			"env": {"DJANGO_SETTINGS_MODULE": "lecture_system.test_settings"},
			"console": "integratedTerminal",
			"justMyCode": true
		},
		{
			"name": "Lecture: Chat persistence test",
			"type": "debugpy",
			"request": "launch",
			"program": "${workspaceFolder}/backend/manage.py",
			"cwd": "${workspaceFolder}/backend",
			"args": [
				"test",
				"core.tests.test_chat_usecase.ChatUsecaseTests.test_run_creates_assistant_message",
				"--verbosity",
				"2"
			],
			"env": {"DJANGO_SETTINGS_MODULE": "lecture_system.test_settings"},
			"console": "integratedTerminal",
			"justMyCode": true
		}
	]
}
```

1. テストメソッドと、追跡する実装の実行可能な行にブレークポイントを置きます。
2. 「実行とデバッグ」で対象の設定を選択し、`F5` で起動します。
3. 「変数」「ウォッチ」「コールスタック」「デバッグコンソール」を開きます。
4. 初めは `justMyCode: true` でアプリケーションを追い、Django や DRF の内部へ進む場合は `false` に変更して再実行します。
5. 別のテストを使う演習では、`args` のテストラベルを、その演習で指定したメソッドへ変更します。

この起動方法は Django のテストランナーを使います。テストファイルを通常の Python ファイルとして直接実行する方法や、標準の unittest discovery だけで起動する方法とは異なります。

ローカル起動と次の Dev Containers の `launch` では、Python Debugger 拡張機能がデバッガーを起動します。Python 環境へ debugpy を別途導入することは、この方法の前提ではありません。3-6 の debugpy attach ではコマンドラインから debugpy を起動するため、一時コンテナへの導入が必要です。

#### Dev Containers で backend コンテナ内から起動する方法(こちらを推奨します！)

Dev Containers を使う場合は、VS Code から backend コンテナを開き、コンテナ内の Python でテストを起動します。接続には Docker を使用するため、コンテナ内の SSH サーバーや SSH 鍵の配置、SSH ポートの公開は不要です。

Docker が別の Linux ホストで動いている場合だけ、先に Remote SSH でその Docker ホストへ接続します。ホストへの接続には既存の SSH 認証を使いますが、コンテナ用の鍵を新しく作成・配置する必要はありません。Docker が受講者の PC で動いている場合は、Remote SSH 自体も不要です。

```text
受講者の PC の VS Code
	→ Remote SSH: Docker ホスト（別ホストの場合だけ使用します）
	→ Dev Containers: backend コンテナを開きます。
	→ コンテナ内の Python で manage.py test を起動します。
```

**1. Docker ホストと拡張機能の確認**

受講者の VS Code に Dev Containers 拡張機能をインストールします。別ホストを使う場合は Remote SSH 拡張機能も有効にし、`Remote-SSH: Connect to Host...` でリポジトリがある Docker ホストへ接続します。接続先の統合ターミナルで `docker version` と `docker compose version` が成功することを確認します。別ホストを使う場合、受講者の PC に Docker を導入する必要はありません。

Docker の操作権限に加え、VS Code Server や拡張機能を導入できるネットワーク接続が必要です。ただし、Docker API を未認証の TCP ポートで公開したり、Docker ソケットを誰でも操作できる権限にしたりしないでください。

**2. テスト用 backend コンテナの準備**

テストだけを実行する場合は、Docker ホストのリポジトリルートで次を実行します。3-2 で説明した backend イメージと Compose の環境変数ファイルを使用します。既存の `lecture-backend-debug` コンテナがある場合は、その用途を確認し、再利用するか別の名前を選びます。

```bash
docker compose run --rm --no-deps --detach \
	--name lecture-backend-debug \
	--volume "$PWD:/workspace" \
	--entrypoint tail backend -f /dev/null
```

`--no-deps` とエントリーポイントの変更により、PostgreSQL・Ollama・API サーバーを起動せず、通常の DB 初期化も実行しません。コンテナを終了させずに接続を待つため、ここでは `tail -f /dev/null` を使います。SSH やデバッグ用のポートは公開しません。

`/workspace` はリポジトリ全体、既存の `/app` は backend ディレクトリを指します。`/workspace/backend` と `/app` が参照するのは、同じホスト上のソースです。Docker ホストでは、本物の秘密情報を含まない演習用の環境変数ファイルを使用してください。

通常起動中の backend コンテナを使う場合は、この作成コマンドを省略できます。ただし、標準 Compose のマウント先は `/app` のみです。後述のデバッグ設定では、backend を基準にしたパスへ変更してください。テスト専用コンテナへの接続と、通常のサービスの起動は別の操作です。

**3. Dev Containers での接続とフォルダーのオープン**

1. Docker ホストを開いている VS Code ウィンドウで、`Dev Containers: Attach to Running Container...` を実行します。
2. テスト用なら `lecture-backend-debug` を、通常起動中のサービスを使うなら対応する backend コンテナを選択します。
3. 新しく開いたウィンドウの左下がコンテナへの接続表示になっていることを確認します。`SSH: ホスト名` だけのウィンドウとは区別します。
4. テスト用コンテナでは「フォルダーを開く」で `/workspace` を開きます。通常の backend コンテナでは `/app` を開きます。
5. コンテナ側に Python 拡張機能と Python Debugger 拡張機能をインストールします。
6. `Python: Select Interpreter` で `/usr/local/bin/python` を選択します。Docker ホスト側の仮想環境のパスは指定しません。

今回は既存コンテナへ接続するので、リポジトリへ `.devcontainer/devcontainer.json` を追加する必要はありません。設定ファイルからコンテナを作成して開く `Dev Containers: Reopen in Container` とは区別します。

再接続時のフォルダーや拡張機能を記憶させたい場合は、接続後に `Dev Containers: Open Named Configuration File` から、テスト用コンテナの接続設定を編集できます。例えば次の設定を使います。既存設定がある場合は必要な項目だけを組み込みます。

```json
{
	"workspaceFolder": "/workspace",
	"extensions": ["ms-python.python", "ms-python.debugpy"]
}
```

この接続設定は `.vscode/launch.json` とは役割が異なります。また、存在しないユーザー名を `remoteUser` に指定しても、そのユーザーは自動では作成されません。[backend/Dockerfile](../../../backend/Dockerfile) は実行ユーザーを指定していないため、既定では root になります。Linux の bind mount では新規ファイルの所有者にも影響するので、講師は必要に応じてホストの UID・GID に対応する開発ユーザーを用意して接続設定を調整します。リポジトリ全体への `chown` で回避しません。

**4. コンテナ内でのテスト実行とデバッグ**

テスト用コンテナで `/workspace` を開いた場合は、統合ターミナルで次を実行します。

```bash
cd /workspace
python backend/manage.py test \
	core.tests.test_auth_api.AuthApiTests.test_login_and_me_only_expose_user_and_expiry \
	--settings lecture_system.test_settings --verbosity 2
```

通常実行が成功したら、`/workspace/.vscode/launch.json` に3-4 のローカル起動と同じ設定を追加します。`${workspaceFolder}` は `/workspace` なので、`program` は `/workspace/backend/manage.py`、`cwd` は `/workspace/backend` になります。

通常の backend コンテナで `/app` を開いた場合は、`cd /app` の後、`python manage.py test` に同じラベルとオプションを渡します。デバッグ設定では、`program` と `cwd` を次のように変更してください。その他の `args`、`env`、`type`、`request` は 3-4 の設定と同じです。

```json
{
	"program": "${workspaceFolder}/manage.py",
	"cwd": "${workspaceFolder}"
}
```

`LoginSerializer.validate()`、`LoginView.post()`、`ChatInSessionUsecase.run()` などにブレークポイントを置き、対象のテスト設定を選択して `F5` で起動します。停止後にコールスタック、変数、モデルの主キー・外部キーを観察します。デバッグコンソールの `__import__("sys").executable` が `/usr/local/bin/python` であることも確認します。

デバッガーもテストもコンテナ内で動くため、ここでは `request: "launch"` を使います。3-6 の `request: "attach"`、`pathMappings`、5678 番ポートの公開は不要です。`DJANGO_SETTINGS_MODULE` は引き続き `lecture_system.test_settings` にして、インメモリ SQLite を使用します。

bind mount 内のコードやデバッグ設定の編集はホスト側にも反映されます。Dev Containers のウィンドウで Docker ホストへの Git 操作まで行う必要はありません。保存した変更はホスト側で確認し、演習用の変更と既存の変更を区別します。

**5. 演習後の接続・テスト用コンテナの終了**

VS Code でデバッグを終了し、コンテナへの接続を閉じます。接続を閉じるだけでは、この方法で手動作成したコンテナは停止しません。Docker ホストで、自分が作成したテスト用コンテナだけを停止します。

```bash
docker stop lecture-backend-debug
```

`--rm` を付けて作成したため、停止するとコンテナは削除されます。bind mount 内の編集ファイルは削除されません。通常起動中の backend を使った場合は、共有サービスをこの手順で停止しません。

接続に失敗した場合は、まず Docker ホストの接続と Docker 操作権限を確認し、続いて Dev Containers の出力ログを確認します。GUI 接続とブレークポイント停止は、講義環境で事前に確認します。詳しくは [実行中のコンテナへの接続](https://code.visualstudio.com/docs/devcontainers/attach-container) と [リモート Docker ホストでの開発](https://code.visualstudio.com/remote/advancedcontainers/develop-remote-host) を参照します。

### 3-5. デバッガーの基本操作

| 操作 | Linux の既定キー | 用途 |
| --- | --- | --- |
| ブレークポイントの切り替え | `F9` | 実行前に停止位置を設定 |
| 続行 | `F5` | 次のブレークポイントまで実行 |
| ステップオーバー | `F10` | 呼び出した関数をまとめて実行し、次の行へ進む |
| ステップイン | `F11` | 呼び出した関数の内部へ進む |
| ステップアウト | `Shift+F11` | 現在の関数から呼び出し元へ戻る |
| 停止 | `Shift+F5` | デバッグ実行を終了 |

OS やキーマップによりキーが違う場合は、デバッグツールバーを使用します。「コールスタック」でテスト側と実装側のフレームを切り替えると、同じ停止時点でも参照できるローカル変数が変わります。

ブレークポイントを右クリックすると、条件やログポイントを設定できます。例えば `user is None` を、`user` が代入済みの行の条件にすると、認証失敗時だけ停止できます。ログポイントはコードを編集せずに確認できますが、秘密情報を出力しないルールは Logger と同じです。

### 3-6. Docker attach を使う場合の代替手順

これはローカル Python に依存関係を導入しない場合の代替です。次のコマンドはリポジトリルートで実行します。debugpy は一時コンテナにだけ導入し、依存定義や Compose ファイルは変更しません。

```bash
docker compose run --rm --no-deps --publish 127.0.0.1:5678:5678 --entrypoint sh backend -c 'python -m pip install debugpy && DJANGO_SETTINGS_MODULE=lecture_system.test_settings python -m debugpy --listen 0.0.0.0:5678 --wait-for-client /app/manage.py test core.tests.test_auth_api.AuthApiTests.test_login_and_me_only_expose_user_and_expiry --verbosity 2'
```

`--wait-for-client` により、VS Code が接続するまでテスト開始を待ちます。起動時のエントリーポイントを変更しているため、通常の DB 待機や初期化処理は実行しません。

デバッグ設定の `configurations` に、次の項目を追加して接続します。

```json
{
	"name": "Lecture: Attach to Docker test",
	"type": "debugpy",
	"request": "attach",
	"connect": {"host": "127.0.0.1", "port": 5678},
	"pathMappings": [
		{"localRoot": "${workspaceFolder}/backend", "remoteRoot": "/app"}
	],
	"justMyCode": true
}
```

5678 番ポートが使用中なら、公開側と `connect.port` を、例えば 5679 番へそろえます。コンテナ内の待ち受けは 5678 番のままにできます。Docker が動くホストと VS Code の拡張機能が動くホストが同じであることを前提にしています。別ホストなら SSH トンネルなどで接続します。

デバッグポートは任意のコードを実行できる入口です。ホスト側では必ずループバックだけに公開し、インターネットや共有ネットワークには公開しません。終了後は一時コンテナとポートが残っていないことを確認します。

### 3-7. Test Explorer を使う場合の補足

基本演習は前述の `F5` 起動で実施できます。Test Explorer を使う場合は、公式の Django 対応手順に従い、unittest を有効にし、環境変数 `MANAGE_PY_PATH` に [manage.py](../../../backend/manage.py) の絶対パスを指定します。同じ環境変数ファイルで `DJANGO_SETTINGS_MODULE=lecture_system.test_settings` も指定します。

例えば、リポジトリルートに演習専用の `.env.debug-tests` を作成します。次の絶対パスは、自分のリポジトリのパスへ変更します。このファイルに本物の認証情報を追加する必要はありません。

```dotenv
MANAGE_PY_PATH=/absolute/path/to/repository/backend/manage.py
DJANGO_SETTINGS_MODULE=lecture_system.test_settings
```

VS Code のワークスペース設定へ、次の項目を追加します。

```json
{
	"python.envFile": "${workspaceFolder}/.env.debug-tests",
	"python.testing.cwd": "${workspaceFolder}/backend",
	"python.testing.unittestEnabled": true,
	"python.testing.pytestEnabled": false,
	"python.testing.unittestArgs": [
		"core.tests.test_auth_api",
		"core.tests.test_chat_usecase"
	]
}
```

`python.testing.unittestArgs` には Django 用のテストラベルを指定し、通常の unittest discovery 用の `-s` や `-p` を混ぜません。pytest の導入はこの講義の前提ではありません。

テスト一覧を更新した後、対象テストの「Debug Test」を選択します。発見に失敗した場合は Python の出力パネルを確認し、先に `manage.py test` の通常実行が成功するか確認します。詳しい設定は末尾の公式資料を参照します。

## 4. 演習 A：Auth API のコード追跡

### A-1. ログイン成功時の処理経路

対象は `AuthApiTests.test_login_and_me_only_expose_user_and_expiry` です。

1. `setUpTestData()` の `create_user()` を読みます。平文のパスワードと、保存される `user.password` が同じか予想します。
2. テストの `login()` を読み、CSRF トークンの取得とログインリクエストが別の処理であることを確認します。
3. `LoginSerializer.validate()` の `authenticate()` 呼び出しにブレークポイントを置きます。
4. `LoginView.post()` の `login()` 呼び出しと `expires_at` の計算にブレークポイントを置きます。
5. テストをデバッグ実行し、入力検証、認証、認証セッションの設定、レスポンス生成の順に停止して観察します。

| 停止位置 | 観察する式 | 確認すること |
| --- | --- | --- |
| `authenticate()` の実行前 | `type(attrs)`、`list(attrs.keys())` | 入力検証後のデータ構造（値全体は記録しない） |
| `authenticate()` の実行後 | `user.pk`、`user.is_active` | 認証成功時に返るユーザーモデル |
| `request.user` への代入後 | `request.user.pk`、`request.session.modified` | ユーザーと認証セッションの状態 |
| 期限設定後 | `expires_at`、`request.session.get_expiry_date()` | アプリケーション側とセッション側の期限の比較 |
| テストでレスポンスを受け取った後 | `response.status_code`、`set(response.data.keys())` | 応答で公開される情報がユーザー情報と期限だけか |

ブレークポイントでは、指定した行の実行前に停止します。その行で作成される変数は、ステップ実行後に観察してください。デバッグコンソールの式は、現在選択しているスタックフレームの変数を参照します。

View が受け取るのは DRF の Request で、`request._request` は内部の Django リクエストです。現在の実装は Django の `login()` へ内部のリクエストを渡し、その後に DRF 側の `request.user` も明示的に代入します。その代入前後を混同しないようにします。

`authenticate()` の先は Django の認証バックエンドへ進みます。ユーザー検索やパスワード照合は、`LoginView` が直接 SQL を組み立てて行う処理ではありません。必要に応じてライブラリ側へステップインし、実際の呼び出し先を確認します。

ライブラリを追う際は、Django の `ModelBackend.authenticate()`、`UserModel._default_manager.get_by_natural_key()`、`user.check_password()` が観察点です。ユーザー検索の SQL と、Python 側のパスワードハッシュ照合を区別します。

`request.session` への代入は、直ちにすべての値を DB に保存する操作ではありません。`login()` がセッションキーを更新する過程でも DB 操作が発生しますが、変更した認証情報や期限の保存は、レスポンス処理の `SessionMiddleware.process_response()` でも行われます。View の `return` だけを見て、保存処理全体が終わったと判断しないようにします。

`justMyCode` を `false` にして `SessionMiddleware.process_response()` と DB セッションバックエンドの `SessionStore.save()` にブレークポイントを置き、テストの API 応答を受け取るところまで追います。実際のセッションバックエンドは、設定を読み込んだフレームで `__import__("django.conf", fromlist=["settings"]).settings.SESSION_ENGINE` を評価して確認します。現在は Django 既定の DB セッションを使います。

### A-2. 認証セッションが無効化される場面

対象は `AuthApiTests.test_logout_invalidates_server_session_and_replayed_cookie` です。

1. テストにある `Session.objects.filter(...).exists()` に注目します。
2. `LogoutView.post()` の `logout(request._request)` で停止します。
3. ログアウト前に認証セッションのレコードが存在することを確認します。
4. ステップ実行後と、API の応答を受け取った後の状態を比較します。
5. 以前の Cookie を再送しても、認証できないことをテストのアサーションで確認します。

Cookie の削除と、サーバー側の認証セッションの無効化は別の観察点です。Cookie の値を資料やログに貼り付けず、`exists()` の真偽と HTTP ステータスだけを記録します。

### A-3. 有効期限と更新処理

対象は `AuthApiTests.test_server_checks_deadline_even_if_session_storage_lives_longer` です。

このテストでは、`Session.objects.filter(...).update(expire_date=...)` で保存期限を延長した後、時刻をモックして API を呼び出します。データベースの保存期限だけが延びても、ログイン時に決めた期限を越えると認証できないことを確認します。

1. `update()` の対象と、変更するフィールドを確認します。
2. `FixedExpirySessionAuthentication.authenticate()` の `timezone.now() >= expiry` にブレークポイントを置き、期限切れの判定を確認します。
3. 最後の `exists()` で、該当する認証セッションが残っているか確認します。
4. 「認証エラーになること」と「レコードを無効化すること」を別々に説明します。

追加で `test_fixed_expiry_boundary_and_replayed_cookie` を実行し、期限の 1 秒前は認証でき、期限と同時刻では認証できないことを確認します。`patch("django.utils.timezone.now", ...)` を使うため、実際に 12 時間待つ必要はありません。

### 復習項目

- `400`、`401`、`403` が、入力・認証・CSRF のどの失敗を表すか、既存テストを根拠に説明します。
- `create_user()` と `objects.create()` の違いを、パスワードの保存方法から説明します。
- `force_login()` だけで、このリポジトリの認証用期限まで設定されるか、`test_session_without_login_deadline_is_rejected` を根拠に説明します。

## 5. 演習 B：Session API の保存処理

### B-0. 会話の作成と取得

作成 API は、`POST /api/sessions/` から Router、`ModelViewSet.create()`、`ChatSessionCreateSerializer`、`perform_create()`、`serializer.save()` を経て、モデルの作成へ進みます。Serializer の `llm` は、入力された ID をもとに関連する `LLM` を検証するフィールドです。

作成時は `llm` が必須で、`uuid` は読み取り専用です。入力の辞書、`validated_data`、作成済みの `serializer.instance` を比較します。Serializer がモデルを表現することと、モデルを DB に保存することを区別します。

HTTP 経路も観察するため、次のメソッドを演習用に [test_chat_usecase.py](../../../backend/core/tests/test_chat_usecase.py) の `ChatUsecaseTests` に追加します。クラス内の既存メソッドと同じ深さにインデントします。既存の `setUp()` の LLM を再利用します。以降の追加メソッドも同じクラスに追加します。

```python
def test_session_api_round_trip(self):
	from django.contrib.auth import get_user_model
	from rest_framework.test import APIClient

	user = get_user_model().objects.create_user(
		username="api-student", password="test-password"
	)
	client = APIClient()
	client.force_authenticate(user=user)
	created = client.post(
		"/api/sessions/",
		{"llm": self.llm.pk, "title": "ORM practice"},
		format="json",
	)
	self.assertEqual(created.status_code, 201)
	session_uuid = created.data["uuid"]
	stored = ChatSession.objects.get(uuid=session_uuid)
	self.assertEqual(stored.llm_id, self.llm.pk)
	self.assertEqual(stored.messages.count(), 0)

	with patch("core.usecases.build_llm_client") as factory:
		factory.return_value.chat.return_value = ChatResult(
			content="Hello from mock", usage={}
		)
		response = client.post(
			f"/api/sessions/{session_uuid}/chat/",
			{"message": "Hi"},
			format="json",
		)
	self.assertEqual(response.status_code, 200)
	listed = client.get(f"/api/sessions/{session_uuid}/messages/")
	self.assertEqual(listed.status_code, 200)
	self.assertEqual(
		[item["role"] for item in listed.data], ["user", "assistant"]
	)
	deleted = client.delete(f"/api/sessions/{session_uuid}/")
	self.assertEqual(deleted.status_code, 204)
	self.assertFalse(ChatSession.objects.filter(uuid=session_uuid).exists())
	self.assertEqual(Message.objects.filter(session_id=session_uuid).count(), 0)
```

実行ラベルは `core.tests.test_chat_usecase.ChatUsecaseTests.test_session_api_round_trip` です。この追加テストでは `force_authenticate()` で認証・CSRF の経路を省略しています。Session API に集中するための方法であり、Auth API の正しさを検証するテストではありません。

`APIClient()` は既定で CSRF チェックを無効にします。さらに `force_authenticate()` は認証済みユーザーを直接設定し、本来の `FixedExpirySessionAuthentication` を通しません。CSRF を確認する Auth 演習では、既存テストの `APIClient(enforce_csrf_checks=True)` と実際のログイン経路を使用します。

`ChatSessionViewSet.perform_create()` の `serializer.save()` と `messages()` の `self.get_object()`、`MessageSerializer(...).data` で停止します。削除は標準の `ModelViewSet.destroy()` へ進みます。現在の削除は `is_active=False` にする論理削除ではなく、レコードを削除し、関連メッセージも ORM の `CASCADE` に従って削除します。

### B-1. チャットの処理順の予想

対象は `ChatSessionViewSet.chat()` と `ChatInSessionUsecase` です。既存の `ChatUsecaseTests.test_run_creates_assistant_message` は Usecase を直接呼び出します。View にも停止したい場合は、B-0 の追加テストを使用します。次の順序をコードと照合します。

1. View で `message` を取得し、空文字列でないことを確認します。
2. Usecase のコンストラクターで、指定した UUID の有効な `ChatSession` を取得します。
3. `run()` に入り、ユーザーメッセージを作成します。
4. `self.session.messages.all()` を走査して、LLM に渡す会話履歴を作成します。
5. 対象の LLM クライアントを作成し、`client.chat()` を呼び出します。
6. 応答からアシスタントメッセージを作成します。
7. 応答用の辞書を返します。

`ChatInSessionUsecase.__init__()` の `get()` と、`run()` の保存処理を同じトランザクションだと思い込まないようにします。`@transaction.atomic` が適用されているのは `run()` です。

### B-2. モデルと保存済みデータの観察

| 停止位置 | 観察する式 | 確認すること |
| --- | --- | --- |
| コンストラクターで取得した後 | `self.session.pk`、`self.session.llm_id` | 会話の主キーと外部キーの値 |
| ユーザーメッセージの作成前後 | `self.session.messages.count()` | メッセージが 1 件増えるか |
| 会話履歴の構築後 | `len(messages)`、`[item["role"] for item in messages]` | 今回のユーザーメッセージが履歴に含まれるか |
| LLM 応答後 | `type(result)`、`result.usage` | 外部クライアントの応答から保存へ渡す値 |
| アシスタントメッセージの作成後 | `assistant.pk`、`assistant.session_id`、`assistant.role` | 作成済みモデルに主キーが割り当てられているか |

デバッグコンソールで呼び出す `count()` や `exists()` も、実際に SQL を実行します。変数の観察でもデータベースへの問い合わせが発生し得ることを意識してください。

### B-3. 失敗時の保存結果の予想

`run()` には `@transaction.atomic` があります。`client.chat()` から例外が外へ伝播した場合、同じトランザクション内で先に作成したユーザーメッセージもロールバックの対象になります。

演習では実際の LLM を停止させるのではなく、モックから例外を返して再現します。「例外が発生したこと」と「メッセージが残っていないこと」の両方をテストで確認します。

ロールバックで取り消せるのは、データベースへの変更です。外部 LLM への通信や利用料金、出力済みのログまでは取り消せません。

## 6. 演習 C：ORM が発行する SQL の観察

### C-1. QuerySet の遅延評価

| ORM の操作 | データベースへの主な動作 |
| --- | --- |
| `filter()`、`order_by()`、`select_related()` | 通常は QuerySet を構築するだけで、取得 SQL はまだ実行しない |
| `list(qs)`、QuerySet の走査、`len(qs)` | 未評価の場合は取得 SQL を実行し、結果をキャッシュ |
| `get()` | 1 件を取得する SQL を直ちに実行 |
| `count()`、`exists()` | 未評価なら件数・存在確認の SQL を実行。評価済みなら結果キャッシュを使う場合もある |
| `objects.create()`、`save()` | 作成・更新の SQL を実行。ただし、DB への書き込みとトランザクションのコミットは別 |
| `QuerySet.update()` | 対象レコードを一括更新（各モデルの `save()` は呼び出さない） |
| `delete()` | レコードを削除。関連データの取得・削除などで複数の SQL になる場合がある |

次のメソッドを `ChatUsecaseTests` に追加します。行ごとに止め、予想した SQL 数とテストの結果を比較します。

```python
def test_queryset_and_related_loading(self):
	from django.db import connection
	from django.test.utils import CaptureQueriesContext

	with self.assertNumQueries(0):
		queryset = ChatSession.objects.filter(uuid=self.session.uuid)
	with self.assertNumQueries(1):
		rows = list(queryset)
	self.assertEqual(len(rows), 1)
	with self.assertNumQueries(0):
		list(queryset)
	with self.assertNumQueries(1):
		list(queryset.all())

	with self.assertNumQueries(2):
		plain = ChatSession.objects.get(uuid=self.session.uuid)
		plain_provider = plain.llm.provider
	with self.assertNumQueries(1):
		joined = ChatSession.objects.select_related("llm").get(
			uuid=self.session.uuid
		)
		joined_provider = joined.llm.provider
	self.assertEqual(plain_provider, joined_provider)

	with CaptureQueriesContext(connection) as captured:
		list(self.session.messages.values("id", "role"))
	self.assertEqual(len(captured), 1)
	self.assertIn("SELECT", captured.captured_queries[0]["sql"].upper())
```

実行ラベルは `core.tests.test_chat_usecase.ChatUsecaseTests.test_queryset_and_related_loading` です。テストの `setUp()` が発行する SQL は、ここで囲んだ計測範囲には含まれません。

SQL 数を測る演習では、未評価の QuerySet をウォッチに登録したり、デバッグコンソールで先に `list()` にしたりしません。QuerySet の表示や `repr()` が追加取得を起こし、観察によって計測結果が変わることがあります。

### C-2. SQL とモデルの関係

`CaptureQueriesContext` の終了後に、`captured.captured_queries` をデバッガーで開きます。この演習はダミーデータだけで実施します。認証や実際の会話を対象に SQL 全文を記録しないようにします。

- `SELECT` の対象テーブルと `WHERE` の外部キー条件を探します。
- 実際のテーブル名は `ChatSession._meta.db_table` と `Message._meta.db_table` で確認します。
- `select_related("llm")` を使った取得では、JOIN により関連する LLM をまとめて取得することを確認します。
- `llm_id` の参照と、未取得の `llm` の参照で、追加 SQL の有無が違うことを確認します。
- `Message.Meta.ordering` の `created_at` が取得順に反映されることを確認します。同時刻の行の順序まで保証するものではありません。

`str(queryset.query)` は QuerySet の SQL 表現を確認する方法であり、通常はその取得 SQL を実行しません。ただし、パラメーターを安全に受け渡して実行するための API ではありません。その文字列を実行用 SQL として再利用しません。

### C-3. DB の値と Python のモデルの違い

取得したモデルを保持したまま `QuerySet.update()` を実行すると、保持している Python オブジェクトの属性は自動で更新されません。演習用テスト内で次の順に比較します。

1. `stored = ChatSession.objects.get(uuid=self.session.uuid)` で取得します。
2. `ChatSession.objects.filter(uuid=stored.uuid).update(title="Updated")` を実行します。
3. `stored.title` が以前の値のままか確認します。
4. `stored.refresh_from_db()` の後で `stored.title` を確認します。

UUID はモデルの生成時に既定値で割り当てられるため、UUID があることだけでは保存済みと判断できません。`ChatSession(llm=self.llm)` と `ChatSession.objects.create(llm=self.llm)` を比べ、DB の存在確認を別に行います。

## 7. 演習 D：Logger による処理経路の調査

### D-1. ログ出力とログ設定の違い

[views.py](../../../backend/core/views.py) には `logging.getLogger(__name__)` の利用例があります。調べたいモジュールごとに Logger を取得すると、`core.auth_views` や `core.usecases` のように出力元を区別できます。

現在の Django 設定には、この演習用の明示的な `LOGGING` 辞書はありません。`logger.debug()` を書くだけで、必ず表示されるわけではありません。Logger のレベル、Handler のレベル、伝播先の設定を確認します。

演習用に [test_settings.py](../../../backend/lecture_system/test_settings.py) へ次の設定を追加します。通常設定ではなく、テスト設定に限定します。既存のログ設定を追加済みの場合は、必要な Logger と Handler を組み込む方法で調整します。

```python
LOGGING = {
	"version": 1,
	"disable_existing_loggers": False,
	"formatters": {
		"lecture": {
			"format": "%(asctime)s %(levelname)s %(name)s:%(lineno)d %(message)s"
		}
	},
	"handlers": {
		"console": {
			"class": "logging.StreamHandler",
			"level": "DEBUG",
			"formatter": "lecture",
		}
	},
	"loggers": {
		"core": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
		"django.db.backends": {
			"handlers": ["console"],
			"level": "WARNING",
			"propagate": False,
		},
	},
}
```

`core` の DEBUG ログは表示しますが、SQL 全文は初期状態では表示しません。なお、Django の `DEBUG` 設定と Logger の `DEBUG` レベルは別の設定です。

SQL Logger も試す場合は、ダミーデータの C 演習に限定して `django.db.backends` のレベルを `DEBUG` にします。Django のテストランナーは通常 `DEBUG=False` で実行するため、SQL ログを有効にするには `manage.py test` の `--debug-mode` も指定します。`CaptureQueriesContext` と `assertNumQueries()` は計測中にクエリー記録を有効にするため、このオプションなしでも使用できます。

ローカル実行では、仮想環境を有効にしたリポジトリルートで、次のように指定します。C 演習のメソッドを追加済みであることを確認します。

```bash
python backend/manage.py test core.tests.test_chat_usecase.ChatUsecaseTests.test_queryset_and_related_loading --settings lecture_system.test_settings --debug-mode --verbosity 2
```

VS Code のローカル設定では `args` のテストラベルを変更し、`"--debug-mode"` を 1 要素として追加します。Docker attach の場合は、起動コマンドの `manage.py test` に引数として追加してください。デバッガーの使用と、このオプションによる Django の DEBUG 設定の有効化は別の操作です。

認証セッションの SQL にはセッションキーやセッションデータが含まれます。Auth 演習では SQL Logger を DEBUG にしません。SQL を観察した後は WARNING に戻します。

### D-2. Usecase の要所へのログ追加

[usecases.py](../../../backend/core/usecases.py) のモジュール先頭で、Logger を取得します。

```python
import logging

logger = logging.getLogger(__name__)
```

`run()` の先頭には、会話本文ではなく文字数を記録します。

```python
logger.debug(
	"chat start session=%s message_chars=%d", self.session.pk, len(user_text)
)
```

既存の `result = client.chat(messages, options=options)` を、次の処理に置き換えます。

```python
try:
	result = client.chat(messages, options=options)
except Exception:
	logger.exception("chat failed session=%s", self.session.pk)
	raise
```

アシスタントメッセージの作成後には、識別子だけを記録します。

```python
logger.info(
	"chat prepared session=%s assistant_id=%s", self.session.pk, assistant.pk
)
```

`logger.exception()` は例外ハンドラー内でスタックトレースを記録します。`raise` を残すことで、例外を握りつぶさずに呼び出し元へ伝え、トランザクションのロールバックも妨げません。

この INFO ログは atomic ブロック内の作成処理を記録するもので、コミット済みという意味ではありません。コミット後の通知などを扱う場合は、別途 `transaction.on_commit()` の利用を検討します。

### D-3. 成功時と失敗時のログの比較

1. 既存の会話保存テストを実行し、開始と作成処理のログを確認します。
2. 次章の失敗テストを実行し、開始ログ、失敗ログ、スタックトレースを確認します。
3. `core` のレベルを `INFO` に変え、DEBUG だけが表示されなくなることを確認します。
4. `%(name)s` と `%(lineno)d` から出力元へ戻り、ログの時系列とコールスタックを照合します。
5. Auth の入力検証も観察する場合は、`authenticate()` の後で成功の真偽だけを DEBUG ログに記録します。

| レベル | 演習での使い分け |
| --- | --- |
| DEBUG | 分岐や件数など、調査に必要な詳細情報 |
| INFO | 処理の開始・完了など、通常の経過 |
| WARNING | 処理は継続できるものの、確認が必要な状態 |
| ERROR / exception | 処理の失敗。`exception()` では ERROR レベルのログに例外情報も付加 |

ログには、パスワード、API キー、Cookie、CSRF トークン、リクエスト全体、モデルの `__dict__`、会話本文を出力しません。`logger.debug("message=%s", model)` も、モデルの `__str__()` が本文を返す場合があるため避けます。実際に `Message.__str__()` は会話本文の先頭を含みます。

例外メッセージ自体にも秘密情報が含まれる可能性があります。`logger.exception()` の例はダミー例外で試し、実サービスへの適用では伏字化や出力内容の点検も必要です。識別子や件数であっても、運用環境では個人情報との関連、保存期間、アクセス権を検討します。

## 8. 演習 E：テストによるロールバックの確認

次のメソッドを `ChatUsecaseTests` に追加します。Logger 演習をまだ実施していなくても、ロールバック自体は検証できます。

```python
def test_llm_failure_rolls_back_messages(self):
	before = self.session.messages.count()
	with patch("core.usecases.build_llm_client") as factory:
		factory.return_value.chat.side_effect = RuntimeError(
			"simulated LLM failure"
		)
		with self.assertRaisesRegex(RuntimeError, "simulated LLM failure"):
			ChatInSessionUsecase(self.session.uuid).run("Hi")
	self.assertEqual(self.session.messages.count(), before)
```

実行ラベルは `core.tests.test_chat_usecase.ChatUsecaseTests.test_llm_failure_rolls_back_messages` です。

1. `run()` のユーザーメッセージ作成前、LLM 呼び出し前、テストの最後のアサーションにブレークポイントを置きます。
2. 作成後には、同じ接続からメッセージが見えることを確認します。
3. LLM 呼び出しで例外が発生し、atomic ブロックの外へ伝わることを確認します。
4. 最後のアサーションで件数が元に戻ることを確認します。
5. デバッガーの例外ブレークポイントで Raised Exceptions を有効にし、例外が投げられた時点でも停止します。`assertRaisesRegex()` が捕捉するため、例外はこのテストの失敗ではありません。

`TestCase` 自体もテストをトランザクションで包みます。テスト後の自動的な片付けとは別に、ここではテストメソッドの途中で件数を確認していることが重要です。`connection.in_atomic_block` が `run()` の外でも True になり得るのは、テスト側のトランザクションがあるためです。

発展課題では、演習用変更として `@transaction.atomic` を一時的に外し、この追加テストが失敗するか確認します。外した場合の件数を予想してから実行し、確認後は自分が外した行だけを戻します。元の正常系テストだけでは、失敗時の保存結果を保証できないことを説明します。

## 9. 逐次確認する追加知識

ここまでの演習に関連する事項を整理します。未習の項目は、次回以降の確認課題として扱います。

1. **モデル定義と DB 構造の管理** モデルを変更しただけで DB の列が変わるわけではありません。[migrations](../../../backend/core/migrations) と `makemigrations`、`migrate` の関係を確認します。実データへの適用前には変更内容とバックアップを確認します。
2. **マイグレーション SQL の確認** `sqlmigrate core マイグレーション番号` で SQL を表示できます。番号は既存ファイルから選びます。`showmigrations` の適用状態は接続先 DB に依存するため、設定と接続先を必ず確認します。
3. **アプリケーションの検証と DB 制約の違い** Serializer の入力検証、モデルの `full_clean()`、DB の NOT NULL・UNIQUE・外部キー制約を区別します。通常の `save()` は `full_clean()` を自動では呼びません。
4. **`choices` と DB の CHECK 制約の違い** API を通さず ORM で保存するときの検証も検討します。`role` などの値をどの層で保証するか確認します。
5. **`get()` が 1 件を返さない場合** 0 件なら `DoesNotExist`、複数なら `MultipleObjectsReturned` です。View の `get_object()` と Usecase の直接の `get()` は、HTTP エラーへの変換経路が異なります。特に現在の `chat()` は Usecase の `get()` の例外を独自に 404 へ変換していません。
6. **一括更新と通常の保存の違い** `update()` はモデルの `save()` や保存シグナルを通しません。`auto_now` も自動で更新しないため、`updated_at` の期待値を確認します。`save(update_fields=...)` でも指定対象を意識します。
7. **削除時のモデル間の関係** `PROTECT`、`SET_NULL`、`CASCADE` の違いを、LLM・Agent・Message で説明します。Django の `on_delete` と、DB の外部キーにある SQL の ON DELETE を同一視しません。
8. **関連取得と N+1 問題** 一覧の各行で関連モデルを取得すると SQL が増えます。単一の外部キーには `select_related()`、逆方向の複数件取得には `prefetch_related()` を検討し、SQL 数で確認します。
9. **取得範囲と順序の設計** 全メッセージを毎回読むと履歴に比例して処理量が増えます。ページネーションや取得件数を検討します。安定した順序が必要なら、同一時刻の扱いまで決めます。
10. **読み取りと書き込みに対するインデックスの影響** `Message` の `session` と `created_at` の複合インデックスを確認します。実行計画とデータ量で判断します。`EXPLAIN ANALYZE` は実際に SQL を実行するため、共有環境で安易に使用しません。
11. **atomic と同時実行時の競合** 同じ会話への並行投稿や履歴の取得範囲を検討します。`select_for_update()` や分離レベルを扱う際は、実際の PostgreSQL で検証します。
12. **外部通信を含むトランザクションの長期化** 現在の `run()` は LLM の応答待ちも atomic 内に含みます。ロールバックの利点と、接続保持時間・競合・再試行時の二重送信を合わせて検討します。
13. **SQLite と PostgreSQL の動作の違い** 型、JSON、制約、ロック、分離レベルなどに違いがあります。本番と同じ DB を使う検証は、専用のテスト DB で別途行います。
14. **テスト用 DB の寿命** インメモリ DB は別プロセスと共有できません。別の shell で開いても同じレコードは見えません。`--keepdb` を使っても、この構成でプロセス終了後のデータが永続化されるわけではありません。
15. **目的に応じたテストクラスの選択** `SimpleTestCase` は原則 DB を使わず、`TestCase` は DB を使いトランザクションで隔離します。実際のコミットやロックの挙動には `TransactionTestCase` などを検討します。
16. **コミット後の処理の検証** `TestCase` の外側のトランザクションは通常コミットされません。`on_commit()` のコールバックには `captureOnCommitCallbacks()` や `TransactionTestCase` を目的に応じて使います。
17. **モックを適用する場所** Usecase はクライアント生成関数を自分のモジュールへ import しているため、`core.usecases.build_llm_client` を patch します。定義元だけの patch では置き換わらない場合があります。
18. **時刻と外部サービスの固定** 期限判定にはタイムゾーン付きの日時を使い、境界の直前・同時刻・直後を検証します。通信や現在時刻を固定すると、再現可能なテストになります。
19. **認証を省略するテストと検証するテストの区別** `force_authenticate()` は Session API の調査を容易にしますが、ログインや CSRF の成功を証明しません。このリポジトリでは `force_login()` だけでも独自の期限が不足します。
20. **デバッグ時の観察による副作用** ウォッチの QuerySet 表示、デバッグコンソールの関数呼び出し、モデルの文字列化で追加 SQL や本文表示が起こり得ます。保存・削除・外部通信をデバッグコンソールから不用意に実行しません。
21. **失敗時の証拠の記録** アサーションの期待値と実際値、例外の種類、スタック、SQL 数、使用した設定を記録します。HTTP の成功だけで保存結果まで正しいと判断しません。

## 10. トラブルシューティングと復習項目

### よくある停止・実行の問題

| 症状 | 最初に確認すること |
| --- | --- |
| ブレークポイントで停止しない | デバッグ実行になっているか、対象テストがその関数を通るか、ファイルが実行環境と一致するかを確認。Docker attach では `pathMappings` も確認 |
| Django 内部にステップインできない | `justMyCode` を `false` にして再実行 |
| `ModuleNotFoundError` が発生する | デバッガーの Python、依存関係の導入先、backend を基準にした実行ディレクトリを確認 |
| `ImproperlyConfigured` や設定未読込のエラーが発生する | `manage.py test` で起動し、`DJANGO_SETTINGS_MODULE` がテスト設定を指すか確認 |
| 管理画面でテストのモデルが見えない | PostgreSQL とインメモリ SQLite を混同していないか確認 |
| DEBUG ログが出力されない | Logger と Handler のレベルを確認。SQL の場合は Django のクエリー記録設定も確認 |
| SQL 数のアサーションがデバッグ時だけ変わる | QuerySet のウォッチやコンソール評価で、先に SQL を実行していないか確認 |
| Test Explorer にテストが表示されない | 選択した Python、`MANAGE_PY_PATH`、テスト設定、Python 出力パネルを確認 |

### 完了確認()

- [ ] 認証セッションと会話セッションの違いを説明できる
- [ ] Auth API の入力検証、ユーザー検索、認証セッション保存の経路を追える
- [ ] Session API の作成、チャット、取得、削除と ORM の操作を対応付けられる
- [ ] QuerySet の評価前後と `select_related()` の SQL 数を比較できる
- [ ] Logger の出力レベルを変更し、秘密情報を含めずに処理を追える
- [ ] VS Code でテストを止め、コールスタックとローカル変数を観察できる
- [ ] LLM 例外時のロールバックを、テスト終了前のアサーションで確認できる
- [ ] SQLite とモックの検証で保証できない範囲を説明できる

最後に「どの入力が、どのコードを通り、どの SQL と保存結果につながったか」を 1 例選び、根拠となる関数名と観察結果を添えて説明してください。演習で変更したログ設定とコードも点検し、共有環境へ持ち込まないことを確認します。PRを作るのであれば、`docs/lecture/students/{name}/{title}.md`を作成してそこに格納してください。

### 記録用テンプレート

```text
対象テスト:
実行方法と Python:
Django 設定と DB:
実行前の予想:
ブレークポイントを置いた関数:
コールスタックの経路:
観察した値・件数:
SQL の種類と回数:
期待値と実際値:
結論と未検証の範囲:
```

## 11. 参考資料

- [Django の QuerySet API](https://docs.djangoproject.com/en/5.2/ref/models/querysets/)
- [Django のトランザクション](https://docs.djangoproject.com/en/5.2/topics/db/transactions/)
- [Django のセッション](https://docs.djangoproject.com/en/5.2/topics/http/sessions/)
- [Django のテスト概要](https://docs.djangoproject.com/en/5.2/topics/testing/overview/)
- [Django のテストツール](https://docs.djangoproject.com/en/5.2/topics/testing/tools/)
- [Django のロギング](https://docs.djangoproject.com/en/5.2/topics/logging/)
- [Python の logging](https://docs.python.org/3/library/logging.html)
- [VS Code の Python デバッグ](https://code.visualstudio.com/docs/python/debugging)
- [VS Code の Python / Django テスト](https://code.visualstudio.com/docs/python/testing)
