# エージェントAPI

LLM、system prompt、生成・検索設定を組み合わせたエージェントを管理し、BASIC_CHAT、RAG_CHAT、またはReAct方式のREACT_CHATを実行する。共通仕様は [README.md](README.md) を参照。

## エンドポイント

| メソッド | パス | 概要 | 成功 |
| --- | --- | --- | --- |
| GET | `/api/agents/` | 一覧取得 | 200 |
| POST | `/api/agents/` | 作成 | 201 |
| GET | `/api/agents/{id}/` | 詳細取得 | 200 |
| PUT | `/api/agents/{id}/` | 更新 | 200 |
| PATCH | `/api/agents/{id}/` | 部分更新 | 200 |
| DELETE | `/api/agents/{id}/` | 物理削除 | 204 |
| POST | `/api/agents/{id}/execute/` | エージェント実行 | 200 |

`{id}` はエージェントの整数主キー。`is_active=true` のエージェントのみが取得・更新・削除・実行対象。非アクティブな項目は通常 `404` となる。

## エージェントのフィールド

「必須」はPOST/PUTでの入力要否で、PATCHでは省略できる。作成・更新・詳細取得は同じフィールド構成を返し、一覧はその配列を返す。

| フィールド | 型 | 必須 | 既定値・制約 |
| --- | --- | --- | --- |
| id | integer | 入力不可 | 自動採番。読み取り専用 |
| name | string | 必須 | 最大100文字。空文字・`null` 不可。一意制約なし |
| usecase_type | string | 必須 | `BASIC_CHAT` / `RAG_CHAT` / `REACT_CHAT` のみ作成・更新可 |
| llm | integer | 必須 | 存在するLLMのID。`null` 不可。`LLM.is_active` の制限なし |
| system_prompt | string / null | 任意 | `null`。空文字可 |
| config | JSON | 任意 | `{}`。生成パラメータ、RAG設定、REACT_CHATの `max_steps` 等 |
| tools | JSON | 任意 | `{}`。保存・返却するが、現実装の実行処理では使用しない |
| is_active | boolean | 任意 | `true` |

- モデル上の選択肢に `CUSTOM` はあるが、作成・更新Serializerは `400` の `Unsupported usecase_type` で拒否する。`422` ではない。
- `config` / `tools` に `null` は指定できない。JSONとしてはオブジェクト以外も保存できるが、`config` は実行コードが辞書として扱うためオブジェクトを指定する。
- `config` の各キーの妥当性はCRUD時に検証しない。RAG用の検証は実行時に行う。
- `created_at` / `updated_at` はAPIレスポンスに含めない。

## 作成

`POST /api/agents/`

```json
{
  "name": "基本チャット",
  "usecase_type": "BASIC_CHAT",
  "llm": 1,
  "system_prompt": "You are a helpful assistant.",
  "config": {"temperature": 0.5},
  "tools": {}
}
```

レスポンス: `201 Created`。

```json
{
  "id": 1,
  "name": "基本チャット",
  "usecase_type": "BASIC_CHAT",
  "llm": 1,
  "system_prompt": "You are a helpful assistant.",
  "config": {"temperature": 0.5},
  "tools": {},
  "is_active": true
}
```

RAGエージェントの作成例。LLMの登録と、データソースへのチャンク登録は事前に行う。

```json
{
  "name": "資料検索チャット",
  "usecase_type": "RAG_CHAT",
  "llm": 1,
  "system_prompt": "Answer using the supplied context.",
  "config": {
    "datasource_ids": [1],
    "embed_model": "nomic-embed-text",
    "top_k": 5,
    "retrieval_mode": "MERGE_RANK",
    "temperature": 0.3
  }
}
```

この例は、チャット用LLMをOLLAMAとして登録している場合を想定する。`embed_model` はその接続先で利用可能で、登録済みチャンクと互換性のある埋め込みモデルを選ぶ。

ReActエージェントの作成例。実行に利用できるLLMは有効なOPENAIプロバイダに限られる。

```json
{
  "name": "商品案内 ReAct",
  "usecase_type": "REACT_CHAT",
  "llm": 1,
  "system_prompt": "回答は簡潔な日本語にしてください。",
  "config": {"max_steps": 6}
}
```

`REACT_CHAT` のモデル選択肢はCRUDで受け付けるが、実行時はLLMの `is_active=true`、`provider=OPENAI`、空でない `api_key` と `model` が必要。`config.max_steps` は1から8の整数で、既定値は8。

## 一覧・詳細取得

`GET /api/agents/` は `200 OK` で、作成レスポンスと同じ構成のオブジェクトの配列を返す。対象がなければ `[]`。`GET /api/agents/{id}/` は単一オブジェクトを返す。

どちらもリクエストボディ不要。一覧にページング、検索、usecase_type等のクエリフィルター、並べ替えパラメータはなく、順序も指定されていない。

## 更新・削除

`PUT /api/agents/{id}/` は `name`、`usecase_type`、`llm` が必須。`PATCH /api/agents/{id}/` は指定項目だけを更新する。

```json
{
  "config": {"temperature": 0.2}
}
```

成功時は `200 OK` で更新後オブジェクトを返す。`config` / `tools` は項目全体の置換。RAGエージェントで `config` を更新する際、既存の `datasource_ids` 等を残すなら更新ボディにも含める。

- `is_active=false` への更新後は、このAPIでは再取得・再有効化・削除できない。必要なら管理画面等を利用する。非アクティブな状態で作成した場合も同様。
- system promptを変更しても、既存セッションの保存済みsystemメッセージは書き換えない。
- `DELETE /api/agents/{id}/` は物理削除。`204 No Content`、ボディなし。
- エージェント削除時、関連セッションは削除せず、`ChatSession.agent` を `null` にする。セッションとメッセージは残る。

## 実行リクエスト

`POST /api/agents/{id}/execute/`

| フィールド | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| input | string | 必須 | 入力テキスト。前後空白を除去。空文字・空白だけ・`null` 不可。REACT_CHATでは最大2000文字 |
| session_uuid | string (UUID) | 任意 | 同じエージェントのアクティブな既存セッション。新規作成時は省略する。`null` 不可 |
| options | object | 任意 | LLM生成パラメータの上書き。`null` 不可。REACT_CHATでは `max_steps` のみ使用 |
| retrieval_overrides | object | 任意 | RAG検索設定の上書き。`null` 不可。BASIC_CHAT / REACT_CHATでは使用しない |

```json
{
  "input": "こんにちは",
  "options": {"temperature": 0.3}
}
```

### セッション・メッセージ

- `session_uuid` を省略すると `llm=agent.llm`、`agent=対象エージェント` の新規セッションを作成する。タイトルは `New Session`。
- 指定したUUIDが存在しない、非アクティブ、別エージェントのセッション、エージェント未紐付けなら `404` の `Session not found`。
- 同じ会話を継続する場合は、前回のレスポンスの `session_uuid` を次のリクエストに渡す。
- BASIC_CHAT / RAG_CHATでは、`system_prompt` が空でなく、セッションに `system` メッセージがまだなければ1度だけ保存する。RAGの検索コンテキストは別途毎回追加する。
- BASIC_CHAT / RAG_CHATではユーザー入力を保存し、既存のsystem・user・assistant等の全履歴をLLMへ送信する。生成には現在の `agent.llm` を使う。
- BASIC_CHAT / RAG_CHATの実行全体を包むDBトランザクションはない。設定検証や外部呼び出しに失敗しても、新規セッション・systemメッセージ・ユーザー入力等が途中まで残る場合がある。リトライの重複排除もない。

#### REACT_CHATのセッション処理

- `session_uuid` を省略した場合、Runnerが最終回答を返した後に新規セッションとuser/assistantメッセージを作成する。3件の作成は同じDBトランザクション内で行う。実行に失敗した場合、空のセッションやメッセージは作成しない。
- 既存セッションでは、対象Agentに属し、アクティブで、`session.llm` が現在の `agent.llm` と一致する必要がある。前提を満たさない会話は `404 Session not found`、LLM不一致は `422`。
- モデルには過去のuser/assistantメッセージと今回の入力を渡す。Agentの `system_prompt` は固定のReAct指示に追記して各モデル呼び出しに渡し、DBのsystemメッセージには保存しない。ツール呼び出し内容も会話履歴として保存しない。
- 成功時に今回のuserとassistantメッセージを保存する。実行失敗時は既存セッションにも今回のメッセージを保存しない。

### 生成パラメータ

優先順位は `llm.extra < agent.config < request.options`。同名キーは右側を優先する浅いマージ。

Viewは以下の検索用キーをマージ結果から除いた `chat_options_only` をLLMクライアントへ渡す。

```text
datasource_ids, top_k, score_threshold, embed_model, retrieval_mode,
max_context_chars, chunk_merge_strategy, context_template,
citation_snippet_chars, dedup_strategy
```

検索設定は `agent.config` と `retrieval_overrides` から解決し、`options` に検索用キーを書いても検索条件の上書きにはならない。`llm.extra` も検索設定の既定値としては使わない。

各クライアントは受け取ったoptionsに加え、`llm.extra` を再び既定値としてマージする。そのため `llm.extra` に検索用キーを置くと、Viewで除外しても外部リクエストへ再混入する場合がある。検索設定は `agent.config` または `retrieval_overrides` に置く。

プロバイダ別の転送キー・usageは [セッションAPI](sessions.md) を参照。

### REACT_CHAT設定と実行

`REACT_CHAT` では、次の優先順位で `max_steps` を決める。

```text
llm.extra < agent.config < request.options
```

右側が同じキーの値を上書きする。`max_steps` の既定値は8、指定可能な範囲は1から8。ReActではこの設定以外の `options` はモデルSDKへ転送せず、`retrieval_overrides` も使用しない。Agent / LLMの既定設定の型・範囲が不正なら `422`、リクエストの `options.max_steps` が不正なら `400`。

ReActの実行は有効なOPENAI LLMのResponses APIを利用する。各モデル応答を1ステップと数え、ツール呼び出しを必要回数繰り返した後、最終回答を得る応答も上限に含める。利用可能なツールは実装で定義された商品価格取得と四則演算で、Agentの `tools` フィールドから動的に選択するものではない。ツール処理のエラーは結果としてモデルに返されるため、モデルが最終回答できればAPIは成功し得る。

```json
{
  "input": "ノートを3冊買って1000円を支払うと、お釣りはいくらですか？",
  "options": {"max_steps": 4}
}
```

成功時は共通の実行レスポンス形式を使い、`result.message` に保存されたassistantメッセージ、`usage` に全ステップのトークン使用量を返す。usageの各整数値はモデルAPIが返した値をステップ間で合算する。

```json
{
  "agent_id": 7,
  "session_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "result": {
    "message": {
      "id": 42,
      "role": "assistant",
      "content": "ノート3冊は750円なので、お釣りは250円です。"
    }
  },
  "usage": {
    "input_tokens": 400,
    "output_tokens": 80,
    "total_tokens": 480
  }
}
```

## BASIC_CHATレスポンス

成功時は `200 OK`。

```json
{
  "agent_id": 1,
  "session_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "result": {
    "message": {
      "id": 3,
      "role": "assistant",
      "content": "こんにちは。"
    }
  },
  "usage": {
    "eval_count": 18
  }
}
```

`result.message` は保存した回答の `id`、固定値 `assistant` の `role`、`content`。BASIC_CHATでは `citations` フィールドを含めない。

## RAG_CHAT検索設定

検索は `agent.config` を基に、`retrieval_overrides` の以下のキーだけを上書きする。未対応の上書きキーは無視する。

| キー | 期待する型 | 既定値 | 動作・検証 |
| --- | --- | --- | --- |
| datasource_ids | array of integer | なし。必須 | 空・未指定は `422`。配列要素やDB上の存在を検証するSerializerはない |
| top_k | integer | 5 | `int` に変換し1以上100以下を検証。各データソースでの取得上限 |
| score_threshold | number | 0.0 | `float` に変換。これより小さいスコアを除外。0以上1以下という範囲検証はない |
| embed_model | string | 未指定 | 検索質問の埋め込みモデル。未指定なら `agent.llm.model` |
| retrieval_mode | string | `UNION` | `UNION` はデータソース順、`MERGE_RANK` は全ヒットをスコア降順に並べ替え |
| max_context_chars | integer | 8000 | 結合したチャンク本文の切り詰め長。`int` 変換のみで正数制約なし |
| chunk_merge_strategy | string | `NEWLINE` | `TITLE_PREFIX` ではタイトル付き、その他は本文のみ。チャンク間は改行で連結 |
| context_template | string | 後述 | `{{chunks}}` と `{{question}}` の両方が必須 |
| citation_snippet_chars | integer | 200 | 引用snippetの切り詰め長。`int` 変換のみで正数制約なし |
| dedup_strategy | string | `NONE` | `HASH_EXACT` では本文のPythonハッシュで重複排除。それ以外は排除しない |

`retrieval_mode` 等の列挙値を厳密に検証する実装ではない。`MERGE_RANK` 以外は並べ替えをせず、未知の値が自動的に `422` になるわけではない。正数制約がない項目も、意図した動作のため正の整数を指定する。

既定の `context_template`:

```text
You are a RAG assistant.
Relevant Info:
{{chunks}}
User: {{question}}
```

### RAG実行例

```json
{
  "input": "RAGの仕組みを説明してください",
  "retrieval_overrides": {
    "datasource_ids": [1],
    "top_k": 3,
    "score_threshold": 0.2,
    "retrieval_mode": "MERGE_RANK"
  },
  "options": {"temperature": 0.2}
}
```

### 検索・コンテキスト構築

1. 検索設定を検証し、質問を `agent.llm` の接続先・providerで埋め込む。`embed_model` があればモデル名だけを上書きする。
2. `datasource_ids` の各 `datasource_{id}` コレクションを検索する。各コレクションで `top_k` 件を要求する。
3. スコア閾値で除外し、指定された場合に全体を順位付け・重複排除する。
4. チャンク本文を改行で結合し、`max_context_chars` を超えたら切り詰めて `...` を付ける。
5. テンプレートの `{{chunks}}` と `{{question}}` を置換し、`metadata={"rag_context":true}` の `system` メッセージとして追加する。
6. ユーザー入力を追加し、全履歴から回答を生成・保存する。

注意事項:

- 質問の埋め込みには **データソース側のLLMではなく、エージェント側のLLM** を使う。チャンク登録時の埋め込みモデル・ベクトル空間との互換性は自動検証しない。埋め込み対応providerはOLLAMA/OPENAI。
- DBのデータソース存在確認・`is_active` の検証はしない。コレクションが残っていれば、非アクティブなデータソースも検索され得る。
- コレクション取得・個別検索の例外はスキップする。全件ヒットなしでも空コンテキストでLLMを呼び、成功レスポンスとなり得る。
- `top_k` は全体上限ではない。複数データソースでは合計引用数が `top_k` を超える場合がある。
- 通常の距離0以上1以下では `score=1-distance`。負の距離は0、1を超える距離は `max(0, 2-distance)` とする。距離尺度の設定自体をAPIでは指定しない。
- 文字数上限は今回結合するチャンク部分だけに適用する。テンプレート・質問・過去履歴・追加の `...` まで含めたプロンプト全体の上限ではない。
- 各回のRAGコンテキストも履歴に残る。過去コンテキストの削除・履歴のトリミングは行わない。

## RAG_CHATレスポンス

成功時は `200 OK`。BASIC_CHATの構成に `result.citations` と `usage.retrieval` を追加する。

```json
{
  "agent_id": 2,
  "session_uuid": "550e8400-e29b-41d4-a716-446655440001",
  "result": {
    "message": {
      "id": 7,
      "role": "assistant",
      "content": "RAGは検索した資料を使って回答を生成します。"
    },
    "citations": [
      {
        "datasource_id": 1,
        "chunk_id": "660e8400-e29b-41d4-a716-446655440000",
        "title": "RAG概要",
        "score": 0.85,
        "rank": 1,
        "snippet": "RAG combines search and generation."
      }
    ]
  },
  "usage": {
    "eval_count": 40,
    "retrieval": {
      "datasources": [1],
      "total_candidates": 1,
      "used_chunks": 1,
      "top_k_requested": 3
    }
  }
}
```

| 引用フィールド | 型 | 説明 |
| --- | --- | --- |
| datasource_id | integer | 検索対象のデータソースID |
| chunk_id | string | ChromaのチャンクID |
| title | string / null | チャンクのタイトル |
| score | number | 距離から変換し小数4桁に丸めたスコア |
| rank | integer | 返却順に1から採番 |
| snippet | string | 本文の先頭 `citation_snippet_chars` 文字。残りがあれば `...` を付ける |

| usage.retrievalのキー | 型 | 説明 |
| --- | --- | --- |
| datasources | array of integer | 指定したデータソースID。実際に検索成功したものだけの一覧ではない |
| total_candidates | integer | 閾値判定・重複排除後のヒット数 |
| used_chunks | integer | 現実装では `total_candidates` と同じ |
| top_k_requested | integer | 各コレクションに要求した件数 |

コンテキストを文字数で切り詰めても引用一覧・件数は切り詰め前のヒット集合を基に生成する。`used_chunks` がすべてプロンプト内に全文収録されたことを意味するわけではない。

## エラー

| ステータス | 条件・レスポンス |
| --- | --- |
| 400 | CRUD必須項目不足、未対応usecase_type、不正な関連LLM等 |
| 400 | executeの必須input不足・空白、UUID形式不正、options等の型不正・`null`。項目別エラー |
| 400 | REACT_CHATのinputが2000文字を超える、または `options.max_steps` が1–8の範囲外・整数でない |
| 404 | エージェント不存在・非アクティブ |
| 404 | 再利用セッション不適合: `{"detail":"Session not found"}` |
| 422 | REACT_CHATでLLMが非アクティブ・OPENAI以外・APIキーまたはモデル名が不正、Agent/LLMの `max_steps` 設定が不正。ReAct構成エラーは `detail` 付き |
| 502 | REACT_CHATのモデル応答が未完了・拒否・空回答、ステップ上限、またはOpenAI APIエラー: `{"detail":"ReAct execution failed"}` |
| 504 | REACT_CHATの外部LLM APIタイムアウト: `{"detail":"LLM request timed out"}` |
| 422 | RAGのdatasource_ids未指定・空: `{"detail":"datasource_ids required"}` |
| 422 | RAGのtop_k範囲外: `{"detail":"retrieval param invalid: top_k"}` |
| 422 | テンプレートの必須プレースホルダー不足: `{"detail":"context_template placeholders missing"}` |
| 400 | RAG処理で捕捉したその他の `ValueError`。`detail` に例外の文字列を返す |
| 500になり得る | 外部LLMの接続・HTTP・タイムアウトエラー、埋め込み失敗、型不正などの未処理例外 |

空のinputは通常Serializerが項目別 `400` にする。Viewにも `{"detail":"input is required"}` の追加チェックがある。

RAGの数値変換失敗は、範囲外top_k用の `422` と同じではなく、通常はその他の `ValueError` として `400`。一方、`TypeError` 等はこの例外処理の対象外。

チャンク登録APIとは異なり、このexecuteは `EmbeddingError` を `422` へ変換しない。埋め込み失敗を含む未処理例外のレスポンス形式は保証しない。

## 実装参照

- [AgentViewSet・execute](../../../backend/core/views.py)
- [AgentSerializer・AgentCreateUpdateSerializer・AgentExecuteSerializer・ReActExecuteSerializer・ReActSettingsSerializer](../../../backend/core/serializers.py)
- [Agent・ChatSession](../../../backend/core/models.py)
- [RagChatRunner・検索設定・引用生成](../../../backend/core/rag_runner.py)
- [ReActAgentUsecase・メッセージ保存](../../../backend/core/react_usecases.py)
- [ReActRunner・ツール実行ループ](../../../backend/core/react_runner.py)
- [ReAct用OpenAIクライアント](../../../backend/core/react_clients.py)
- [ReActツール定義](../../../backend/core/react_tools.py)
- [埋め込み生成](../../../backend/core/datasource_store.py)
- [LLMクライアント](../../../backend/core/llm_clients.py)
