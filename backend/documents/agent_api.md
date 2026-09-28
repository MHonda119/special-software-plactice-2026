# Agent API 仕様 (Draft v2)

最終更新: 2025-11-09

## 1. 概要
Agent API は **LLM 設定 (LLM API)** と **会話セッション (Chat Session API)**、将来的には **データソース / ツール** など複数リソースを統合し、ユースケース指向で「実行 (execute)」操作を行う上位レイヤです。Agent はチャットに限定されず、RAG、解析、ツール呼び出し型など多様な振る舞いを内包できます。v2 Draft では **名称整理** (chat→execute) および **config の汎用化** を反映し、RAG 特化設定の過剰露出を排除しました。

## 2. 背景 / 目的
現状 UI/クライアントは LLM と Session の直接操作でチャットを構成。用途別 (例: 単純 QA / RAG / 計算ツール混在) の前処理・後処理を差し込む統一抽象がない。

目的:
- UsecaseType ごとに異なる前後処理 (コンテキスト拡張 / 構造化抽出 / ツール実行) を統合。
- セッション継続・履歴管理・LLM 選択・オプションマージを一元化。
- 将来 RAG / ツール連携 / ストリーミング等の拡張を段階導入可能なスケルトンを確立。

## 3. 用語定義
| 用語 | 説明 |
|------|------|
| Agent | ユースケースとメタ構成 (LLM, system_prompt, config など) を束ねる抽象エンティティ |
| UsecaseType | Agent が提供する振る舞いの種別 (BASIC_CHAT / RAG_CHAT / CUSTOM 等) |
| Execute | Agent に対し 1 回の入力を与え、応答 (メッセージ/結果) を取得する操作。チャットだけでなく汎用出力を包含 |
| Session | (オプション) 連続する execute 呼び出しの状態保持単位。既存 `ChatSession` を拡張利用 |
| DataSource (将来) | RAG 等で参照する文書/構造化データ集合 |
| Tool (将来) | 外部 API / 関数 / 計算資源など呼び出し可能な拡張手段 |

## 4. スコープ (v1 実装想定 / 本 Draft 対象範囲)
- UsecaseType: `BASIC_CHAT` のみ実装対象
- execute 処理は LLM へのシンプルなチャット問い合わせ
- RAG / Tool / Custom ロジックは未実装 (仕様 placeholder のみ)

## 5. ドメインモデル
### 5.1 Agent モデル (更新後)
| フィールド | 型 | 必須 | 説明 |
|------------|----|------|------|
| id | integer | - | PK |
| name | string(<=100) | 必須 | 表示名 |
| usecase_type | enum | 必須 | `BASIC_CHAT` / `RAG_CHAT` / `CUSTOM` (v1: BASIC_CHAT のみ accept) |
| llm | FK(LLM) | 必須(現状) | 使用する LLM 設定 (将来 optional でマルチ戦略化) |
| system_prompt | text | 任意 | 先頭に注入するシステムメッセージ (重複回避) |
| config | JSON | 任意 | UsecaseType 汎用設定 (RAG 専用ではない) |
| tools | JSON | 任意 | 将来のツール定義メタ (一覧/有効化 flags) |
| is_active | bool | 任意 (default true) | 無効化で一覧/execute 対象外 |
| created_at | datetime | - | 生成時間 |
| updated_at | datetime | - | 更新時間 |

変更点:
- 旧 `rag_config` を廃止し `config` に統合。
- RAG 特化キーは UsecaseType 別セクションで記述。

### 5.2 Session 拡張案
既存 `ChatSession` に `agent` FK を追加 (null 許容移行 → 将来 NOT NULL)。
| 追加フィールド | 型 | 説明 |
|----------------|----|------|
| agent | FK(Agent, null=True) | Agent 経由で生成されたセッションを識別 |

### 5.3 Message (再利用)
変更なし。system_prompt を初回だけ永続化 or 毎回オンザフライ挿入方式は選択可。v1 は永続化 (重複防止ロジック) を推奨。

## 6. UsecaseType 別 config キー例 (ガイドライン)
| UsecaseType | 想定代表キー | 説明 |
|-------------|--------------|------|
| BASIC_CHAT | temperature, top_p, max_tokens | LLM 生成挙動制御 |
| RAG_CHAT (将来) | embed_model, top_k, score_threshold, chunk_merge, context_template | コンテキスト検索/構築制御 |
| CUSTOM | strategy, steps[], output_format, validation_rules | ワークフロー/出力構造定義 |

Validation 方針: usecase_type ごとに許可キー whitelist + 型検証 (将来拡張)。v1 は緩やかに dict 受容。

## 7. Execute 処理フロー (BASIC_CHAT)
1. `POST /api/agents/{id}/execute/` 受信
2. Agent 取得 & is_active 確認
3. `session_uuid` 指定なし: 新規 Session (agent FK 設定) 作成
4. system_prompt (存在 & 未挿入) を最初の system Message として保存
5. ユーザ入力メッセージ保存
6. 履歴メッセージを LLM クライアントへ (options マージ適用)
7. 応答保存 (assistant)
8. 正規化 usage と共にレスポンス返却

### シーケンス
```
Client -> API: POST /api/agents/1/execute {input, session_uuid?}
API -> DB: Load Agent
API -> DB: Load/Create Session(agent=1)
API -> DB: (optional) Insert system
API -> DB: Insert user
API -> LLM Client: chat(messages, final_options)
LLM Client -> External LLM: POST ...
External LLM -> LLM Client: response
LLM Client -> API: ChatResult
API -> DB: Insert assistant
API -> Client: {agent_id, session_uuid, result, usage}
```

## 8. エンドポイント定義
ベースパス: `/api/agents/`
| メソッド | パス | 説明 |
|----------|------|------|
| GET | /api/agents/ | Agent 一覧 |
| POST | /api/agents/ | Agent 作成 |
| GET | /api/agents/{id}/ | 単一取得 |
| PUT | /api/agents/{id}/ | 全更新 |
| PATCH | /api/agents/{id}/ | 部分更新 |
| DELETE | /api/agents/{id}/ | 削除 or 論理無効化 |
| POST | /api/agents/{id}/execute/ | 実行 (チャット/BASIC_CHAT) |
| GET | /api/agents/{id}/sessions/{uuid}/messages/ | セッション履歴取得 (将来) |

## 9. リクエスト / レスポンス例
### 9.1 Agent 作成 (POST /api/agents/)
```json
{
  "name": "Basic Chat Bot",
  "usecase_type": "BASIC_CHAT",
  "llm": 1,
  "system_prompt": "You are a helpful assistant.",
  "config": {"temperature": 0.7}
}
```
レスポンス (201):
```json
{
  "id": 10,
  "name": "Basic Chat Bot",
  "usecase_type": "BASIC_CHAT",
  "llm": 1,
  "system_prompt": "You are a helpful assistant.",
  "config": {"temperature": 0.7},
  "tools": {},
  "is_active": true
}
```

### 9.2 実行 (POST /api/agents/{id}/execute/)
```json
{
  "input": "RAG とは?",
  "session_uuid": "<既存UUID or 省略>",
  "options": {"temperature": 0.2}
}
```
レスポンス例:
```json
{
  "agent_id": 1,
  "session_uuid": "2f52c5c5-...",
  "result": {
    "message": {
      "id": 123,
      "role": "assistant",
      "content": "RAG は Retrieval Augmented Generation の略で ..."
    }
  },
  "usage": {"eval_count": 3456}
}
```

備考: 将来 `result` は型拡張 (例: {"message":..., "citations":[], "tool_calls":[]})。

## 10. シリアライザ / バリデーション案
- `AgentSerializer` (GET): `id,name,usecase_type,llm,system_prompt,config,tools,is_active`
- `AgentCreateUpdateSerializer`: usecase_type 制限 (BASIC_CHAT), llm 必須, config dict
- `AgentExecuteSerializer` (入力): `input (str required)`, `session_uuid (uuid optional)`, `options (dict optional)`
- `AgentExecuteResponseSerializer` (出力): `agent_id, session_uuid, result, usage`

## 11. オプションマージ仕様
`final_options = {**llm.extra, **agent.config, **request.options}`  (右側優先)
Gemini 等プロバイダ特有フィールド制限は既存クライアント実装再利用。

## 12. エラー
| ステータス | 例 | 原因 |
|------------|----|------|
| 400 | {"detail":"input is required"} | 入力未指定/空 |
| 404 | - | Agent / Session 不存在 or inactive |
| 422 | {"detail":"Unsupported usecase_type"} | 未実装タイプ指定 |
| 500 | - | LLM 呼び出し失敗 |

## 13. セキュリティ / 運用
| 項目 | 現状 | 将来案 |
|------|------|--------|
| 認証 | 無し | Token / OAuth2 / Key-based |
| アクセス制御 | 無し | Agent 所有者 / ロールベース |
| レート制限 | 無し | Agent 単位 Throttle |
| ログ | 標準 | Input/Output マスク, 監査ログ |

## 14. パフォーマンス / 並行性
- 同時 execute: トランザクション内で atomic。大量並行時はメッセージフェッチ最適化 (select only needed fields)。
- 履歴肥大: ページング, 要約, windowing 将来導入。

## 15. 拡張 (RAG_CHAT / CUSTOM) 概要
### 15.1 RAG_CHAT
追加ステップ: クエリ埋め込み → 検索 (top_k) → コンテキスト合成 (template) → LLM
config 例キー: `embed_model`, `top_k`, `score_threshold`, `context_template`
`result` 拡張: `{ message, citations: [{doc_id, score, snippet}], usage }`

**embed_model 取り扱いガイド:** Datasource 登録時に使用した埋め込み LLM (`datasource.llm.model`) と同じモデル名を `config.embed_model` に指定してください。Agent の対話用 LLM と異なるモデルを設定できるため、RAG_CHAT では必須扱いとし、UI では選択した Datasource から推奨値を自動補完する運用を想定しています。

### 15.2 CUSTOM
Strategy パイプライン: `steps: ["analyze", "fetch_metrics", "draft", "refine"]` など
各 step 実行で Tool 呼び出し / 中間メモ保存。

## 16. 実装コンポーネント設計
| コンポーネント | 役割 |
|---------------|------|
| AgentUsecaseFactory | usecase_type → Runner 生成 |
| BaseAgentRunner | 共通インタフェース `execute(input, session, options)` |
| BasicChatRunner | BASIC_CHAT 実装 (LLM 直呼) |
| RagChatRunner (将来) | 検索 + コンテキスト拡張 |
| CustomRunner (将来) | 拡張ステップ orchestrator |

## 17. マイグレーション戦略
1. `Agent` モデル追加 → M1
2. `ChatSession.agent` nullable 追加 → M2
3. View / Serializer 実装
4. `execute` エンドポイント追加
5. 既存フロントが旧 Session API を利用し続けても影響なし
6. 新 UI が Agent API を段階導入

## 18. テスト項目 (MVP)
- Agent 作成 成功/失敗(usecase_type!=BASIC_CHAT)
- execute: 新規セッション生成 + 応答保存
- execute: 既存セッション継続
- system_prompt 一度のみ保存
- options マージ優先順位
- llm.extra 改変なし保証
- エラーパス: input 空 / Agent inactive

## 19. クイックテスト例
```bash
# Agent 作成
curl -X POST http://localhost:8000/api/agents/ \
 -H 'Content-Type: application/json' \
 -d '{"name":"Basic","usecase_type":"BASIC_CHAT","llm":1,"system_prompt":"You are helpful."}'

# 実行 (新規)
curl -X POST http://localhost:8000/api/agents/1/execute/ \
 -H 'Content-Type: application/json' \
 -d '{"input":"こんにちは"}'
```

## 20. ロードマップ (更新)
| フェーズ | 内容 |
|---------|------|
| v1 | BASIC_CHAT, execute エンドポイント, system_prompt, options マージ |
| v2 | RAG_CHAT (索引管理, コンテキスト挿入) |
| v3 | Tools / CUSTOM, パイプライン Runner |
| v4 | Streaming, 会話要約, Long-term Memory |

---
以上、Agent API Draft v2 (execute / 汎用 config 統合版)。
