# 第6回 バックエンド演習記録：ORM・データベース・テスト・デバッグ

- 作成者: OkazakiArata0106
- ブランチ: `lecture06/okazakiarata0106-orm-debug`
- 実行環境: Dev Containers（`lecture-backend-debug`）の `/usr/local/bin/python`、および `scripts/test-backend.sh`
- Django 設定と DB: `lecture_system.test_settings`、インメモリ SQLite
- 外部 LLM: すべてモックに置き換え（実際の通信なし）

## A-1 ログイン成功時の処理経路

- **対象テスト**: `AuthApiTests.test_login_and_me_only_expose_user_and_expiry`
- **実行方法**: VS Code のデバッガ（Lecture: Auth login test）
- **実行前の予想**: 保存される `user.password` は平文と違う値になる。ログインすると認証セッションが作られる
- **ブレークポイント**:
  - `test_auth_api.py`（33、34行目）
  - `LoginSerializer.validate()`（14、19行目）
  - `LoginView.post()`（41、44行目）
- **コールスタックの経路**: テスト → `APIClient.post` → `LoginView.post` → `serializer.is_valid` → `LoginSerializer.validate` → `authenticate`

### 観察した値

| 停止位置 | 観察した値 |
| --- | --- |
| ① ログイン前（テスト 33行目） | `user.pk=1`、パスワードの方式は `pbkdf2_sha256`（平文ではない）、Session の件数は 0 |
| ② `authenticate()` の前 | `attrs` は `dict`、キーは `username` と `password`（値は記録しない） |
| ③ `authenticate()` の後 | `user.pk=1`、`user.is_active=True` |
| ④ `login()` の後 | `request.user.pk=1`、`request.session.modified=True` |
| ⑤ 期限の設定後 | `expires_at` と `get_expiry_date()` は一致（ログインの12時間後、UTC） |
| ⑥ ログイン後のレスポンス | `status=200`、キーは `user` と `expires_at` のみ |

- **SQL の種類と回数**: 未計測（`authenticate()` でユーザーを検索する SELECT が発生しているはず）
- **期待値と実際値**: status 200、レスポンスのキーは `{user, expires_at}` で一致

### 結論

入力は Serializer で検証され、`authenticate()` でユーザーの検索とパスワードの照合が行われ、`login()` でリクエストとユーザーが結び付けられる。期限はログイン時刻の12時間後に固定される。パスワードはハッシュ化して保存され、レスポンスには含まれない。

### 未検証の範囲

- 認証セッションが DB に保存される正確なタイミング（`SessionMiddleware.process_response`）
- `authenticate()` の内部（`ModelBackend`、`check_password`）
- 発行される SQL の回数

## B Session API の保存処理

- **対象テスト**: `ChatUsecaseTests.test_session_api_round_trip`（資料のコードを追加）
- **実行方法**: `bash scripts/test-backend.sh core.tests.test_chat_usecase`（5件すべて成功）
- **実行前の予想**: 作成 → チャット → 履歴 → 削除の順に動き、会話を削除すると関連メッセージも消える

### 結果（テストのアサーションで確認）

| 操作 | API | 結果 |
| --- | --- | --- |
| 作成 | `POST /api/sessions/` | 201。DB の `llm_id` は指定した LLM と一致し、メッセージは 0 件 |
| チャット | `POST /api/sessions/{uuid}/chat/` | 200 |
| 履歴 | `GET /api/sessions/{uuid}/messages/` | 200。role は `[user, assistant]` の順 |
| 削除 | `DELETE /api/sessions/{uuid}/` | 204。ChatSession も Message も 0 件 |

### 結論

`Message` → `ChatSession` の外部キーが `on_delete=CASCADE` なので、会話を削除すると関連メッセージも ORM が削除する。`is_active=False` にする論理削除ではなく、レコードを消す物理削除になっている。

### 未検証の範囲

- `force_authenticate()` を使ったため、ログインと CSRF の経路は通していない
- デバッガで View の途中（`perform_create()` など）は止めていない

## C ORM が発行する SQL

- **対象テスト**: `ChatUsecaseTests.test_queryset_and_related_loading`（資料のコードを追加）
- **実行方法**: `bash scripts/test-backend.sh core.tests.test_chat_usecase`
- **確認方法**: `assertNumQueries()` と `CaptureQueriesContext` による SQL の回数の検証（すべて成功）

### 結果

| ORM の操作 | SQL の回数 | 理由 |
| --- | --- | --- |
| `ChatSession.objects.filter(...)` | 0 回 | QuerySet を作るだけで、まだ実行しない（遅延評価） |
| `list(queryset)` | 1 回 | ここで初めて SELECT を実行 |
| もう一度 `list(queryset)` | 0 回 | 1回目の結果のキャッシュを使う |
| `list(queryset.all())` | 1 回 | 新しい QuerySet なので再取得 |
| `get()` の後に `.llm.provider` | 2 回 | 会話の取得と、関連する LLM の取得が別々 |
| `select_related("llm").get()` の後に `.llm.provider` | 1 回 | JOIN で会話と LLM をまとめて取得 |
| `messages.values("id", "role")` | 1 回 | SELECT 文が 1 回 |

### 結論

ORM は、結果が必要になった時点で SQL を実行する。関連するモデルを使う場合は、`select_related()` で SQL の回数を減らせる（一覧で関連を参照すると、行ごとに SQL が増える N+1 問題の対策になる）。

### 未検証の範囲

- SQL の全文と JOIN の内容はデバッガで開いていない
- PostgreSQL での実行計画や速度

## D Logger による処理経路の調査

- **変更**: `test_settings.py` に `LOGGING` を追加（`core` は DEBUG、`django.db.backends` は WARNING）、`usecases.py` に Logger を追加
- **実行方法**: `bash scripts/test-backend.sh core.tests.test_chat_usecase`

### 結果

| 場面 | 出たログ |
| --- | --- |
| 成功時 | `DEBUG chat start`（`usecases.py` 18行目）→ `INFO chat prepared`（44行目、`assistant_id` あり） |
| 失敗時（LLM の例外） | `DEBUG chat start` → `ERROR chat failed`（35行目）とスタックトレース。`INFO chat prepared` は出ない |
| `core` を INFO に変更 | `DEBUG chat start` の3行だけが出なくなり、INFO と ERROR は残った |

- スタックトレースから、エラーの発生場所は `usecases.py` 33行目の `client.chat()` だとわかった
- ログには会話の ID、文字数、メッセージの ID だけを出し、会話本文は出していない

### 結論

ログのレベルと出力元（モジュール名と行番号）から、処理の流れと失敗した場所をたどれる。レベルは設定だけで切り替えられ、コードを変える必要はない。

## E ロールバック

- **対象テスト**: `ChatUsecaseTests.test_llm_failure_rolls_back_messages`（資料のコードを追加）
- **実行方法**: VS Code のデバッガ（Lecture: Rollback test）
- **実行前の予想**: LLM でエラーが起きると、先に作ったユーザーメッセージも取り消される
- **ブレークポイント**: `usecases.py` の `build_llm_client` の行、テストの最後のアサーション

### 観察した値

| 停止位置 | 観察した値 |
| --- | --- |
| LLM 呼び出しの直前 | `messages.count()=1`、role は `['user']` |
| テストの最後 | `before=0`、`messages.count()=0` |

### 結論

`run()` には `@transaction.atomic` が付いているので、LLM の例外が外に出ると、同じトランザクションで作ったユーザーメッセージも取り消される（ACID の原子性）。LLM 呼び出しの直前に 1 件見えるのは、同じ DB 接続の中から見ているため。

### 限界

取り消せるのは DB の変更だけ。LLM への通信、利用料金、出力済みのログ（`ERROR chat failed`）は元に戻らない。

## まとめ：入力 → コード → SQL → 保存結果

- **入力**: `POST /api/sessions/{uuid}/chat/` に `{"message": "Hi"}`
- **コード**:
  1. `ChatSessionViewSet.chat()` が入力を受け取る
  2. `ChatInSessionUsecase.__init__()` が `select_related("llm").get()` で会話と LLM を取得
  3. `run()`（`@transaction.atomic`）の中で、ユーザーメッセージを作成し、履歴を取得し、LLM を呼び出し、アシスタントメッセージを作成する
- **SQL**: SELECT（会話と LLM を JOIN）→ INSERT（user）→ SELECT（履歴）→ INSERT（assistant）
- **保存結果**: Message が 2 件（user、assistant）。LLM が失敗した場合は、ロールバックで 0 件に戻る
- **根拠**: B のテスト（role が `[user, assistant]`）、D のログ（`chat start` → `chat prepared`）、E のデバッガ観察（1 件 → 0 件）

## SQLite とモックで保証できない範囲

- PostgreSQL での型、制約、ロック、同時実行の動き（テストはインメモリ SQLite）
- 実際の LLM の応答時間、エラーの種類、利用料金（LLM はモック）
- ログインと CSRF を通した Session API の経路（B では `force_authenticate()` で省略）
- 同じ会話への同時投稿や、LLM の応答待ちでトランザクションが長くなる影響
