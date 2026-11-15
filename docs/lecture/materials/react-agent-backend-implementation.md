# ReAct Agent バックエンド実装資料

## 1. この資料の使い方

[講義構成](react-agent-backend-lecture.md) の演習手順です。[06_react_agent.py](../../../scripts/api_basics/06_react_agent.py) を参考に、既存の Agent 実行 API に ReAct の実行方式を追加します。新しい Route と React のフロントエンド実装は対象外です。

**この資料中の新しいモジュールと `REACT_CHAT` 機能は、演習で追加する完成例です。教材の追加だけでは実装されません。** コードブロックは、表示された対象へ受講者が実装するためのものです。既存のファイル全体を置き換えないでください。

### 演習での変更範囲

```text
backend/
  requirements.txt                 openai SDK の依存を追加
  core/
    react_tools.py                 新規: ツールとスキーマ
    react_runner.py                新規: ReAct の反復処理
    react_clients.py               新規: Responses API クライアントの生成
    react_usecases.py              新規: Agent の会話取得、実行、成功時保存
    models.py                      変更: Agent の choices に REACT_CHAT を追加
    migrations/                    追加: choices の変更を記録する migration
    serializers.py                 変更: Agent 種別の許可値、ReAct の入力検証
    views.py                       変更: 既存 execute の分岐と補助メソッド
    tests/
      test_react_runner.py         新規: 外部 API なしの反復処理テスト
      test_react_usecase.py        新規: DB 保存と履歴のテスト
      test_react_api.py            新規: HTTP 境界のテスト
```

[models.py](../../../backend/core/models.py) の Agent choices と作成・更新 Serializer の両方を変更します。新しい Model やフィールドは不要ですが、choices の変更を migration に記録します。[usecases.py](../../../backend/core/usecases.py) の通常チャットと既存 BASIC_CHAT / RAG_CHAT の処理は維持します。[core/urls.py](../../../backend/core/urls.py) は変更せず、登録済みの `AgentViewSet.execute` を拡張します。演習の完了時には [Agent API 仕様](../../backend/api/agents.md) と [既存の API 資料](../../../backend/documents/agent_api.md) にも、新しい種別と以下の契約を反映します。

### 先に決める API 契約

```http
POST /api/agents/{id}/execute/
Content-Type: application/json

{
    "input": "ノートを3冊買って1000円を支払うと、お釣りはいくらですか？",
    "options": {"max_steps": 8}
}
```

対象は `usecase_type="REACT_CHAT"` の Agent です。初回は `session_uuid` を省略し、継続時は前回の UUID を同じ Agent の `execute` へ送ります。`options.max_steps` の既定値は 8、許可範囲は 1–8 です。最終回答を得る問い合わせも 1 ステップに数えます。価格取得・乗算・減算・最終回答を別々に行う場合は 4 ステップです。

```json
{
    "agent_id": 7,
  "session_uuid": "会話の UUID",
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

上の usage は形式説明用の例です。実際には各ステップで API が返した値を合算します。既存 Agent API と同じ `agent_id` / `session_uuid` / `result.message` / `usage` の形式を維持します。

| 結果 | HTTP | DB に新しい Message を保存するか |
| --- | --- | --- |
| 最終回答が得られた | 200 | user と assistant を両方保存 |
| 空の入力、長すぎる入力、範囲外の上限 | 400 | 保存しない |
| Agent または指定した会話がない、非アクティブ、会話が別 Agent に属する | 404 | 保存しない |
| 非対応・無効な LLM、API キー不足、不正な Agent 設定 | 422 | 保存しない |
| モデルの未完了・拒否・空回答、ステップ上限、外部 API エラー | 502 | 保存しない |
| 外部 API のタイムアウト | 504 | 保存しない |

認証・CSRF は既存の DRF 設定を使います。認証のエラーを上表の業務エラーに置き換えません。モデルが扱えるツールエラーは観測結果として返すため、途中でツールが失敗しても、モデルが最終回答まで進めれば HTTP 200 になります。

初回は Runner の成功後に会話と Message 2 件を同じトランザクションで作成します。失敗した初回リクエストで空の会話も作成しません。この方針は ReAct の分岐に限定し、既存の BASIC_CHAT / RAG_CHAT の保存方法まで変更しません。

## 2. スクリプトをバックエンドの責務へ分解する

| 参照スクリプトの処理 | 移動先 | 変更点 |
| --- | --- | --- |
| `PRODUCT_PRICES`、`TOOLS`、`execute_tool` | Tools | 許可リストと入力検証を維持する |
| `INSTRUCTIONS`、`ReActAgent.run` のループ | Runner | `print` をなくし、過去の会話を入力できるようにする |
| `new_client`、`TEXT_MODEL` | Client の生成と Agent の `LLM` | 配布キーで登録した GPT-6 luna の設定を使う |
| `argparse` と `main` | Serializer / View | HTTP の JSON とルーティングへ置き換える |
| スクリプトにない会話保存 | Usecase / Model | DB 履歴を渡し、成功した質問と回答をまとめて保存する |

講義では、配布 API キーを使って GPT-6 luna を OPENAI として登録します。既存の [llm_clients.py](../../../backend/core/llm_clients.py) の `chat` はツール呼び出しを返す契約ではないため、流用しません。`Agent.tools` に JSON を保存するだけでも、Python 関数が実行可能になるわけではありません。

### 準備: SDK の依存

演習を始める時点で [backend の依存一覧](../../../backend/requirements.txt) に `openai` はありません。演習ブランチでは同ファイルへ次の依存を追加し、授業で使用する SDK のバージョンを統一します。

```text
openai>=2,<3
```

Python 3.12 の backend 開発環境で、依存を再インストールします。環境の作成手順は [既存の演習資料](orm-database-debug-workshop.md) を参照してください。

```bash
python -m pip install -r backend/requirements.txt
```

Docker を使う場合は、依存を追加してから `docker compose build backend` を実行します。CLI 例の `common.py` やその隣の環境変数ファイルを backend に import しません。

### 準備: GPT-6 luna の登録

通常の講義用 backend を起動し、管理画面の LLM 登録フォームへ次の値を入力します。API キーは講義で配布する値を直接入力し、コード・コマンド履歴・チャット・提出物には記載しません。

| フィールド | 登録値 |
| --- | --- |
| `name` | `GPT-6 luna` |
| `provider` | `OPENAI` |
| `model` | `gpt-6-luna` |
| `base_url` | `https://api.openai.com/v1` |
| `api_key` | 講義で配布する API キー |
| `extra` | `{}` |
| `is_active` | `true` |

`base_url` は API のベース URL であり、末尾に `/responses` を付けません。SDK が問い合わせ先を組み立てます。講義環境で別の接続先が案内された場合のみ、その base URL を登録します。表示名と API の model ID は別項目で、`gpt-6-luna` は [common.py](../../../scripts/api_basics/common.py) の既定値と一致させます。

本講義は配布キーでこのモデルを利用する前提です。キーの利用権限、Responses API と function calling、利用枠、接続先は講師が事前に確認します。資料作成時のモック検証は実モデルの疎通確認を代替しません。配布キーは講義用の DB だけに保存し、授業後の削除・失効は講師の案内に従います。

### 手順 0: Agent の実行種別を追加する

[models.py](../../../backend/core/models.py) の `Agent.USECASE_CHOICES` を次に変更します。フィールド定義そのものは維持します。

```python
USECASE_CHOICES = [
    ("BASIC_CHAT", "Basic Chat"),
    ("RAG_CHAT", "RAG Chat"),
    ("REACT_CHAT", "ReAct Chat"),
    ("CUSTOM", "Custom"),
]
```

[serializers.py](../../../backend/core/serializers.py) の `AgentCreateUpdateSerializer.validate_usecase_type` も次に変更します。Model の choices だけでは、この明示的な検証を通過できません。

```python
def validate_usecase_type(self, value):
    if value not in {"BASIC_CHAT", "RAG_CHAT", "REACT_CHAT"}:
        raise ValidationError("Unsupported usecase_type")
    return value
```

backend の実行環境内で次を実行します。コンテナに接続している場合、通常は `/app` が backend のルートです。テスト用設定ではなく、演習用 DB の通常設定で migration を適用します。

```bash
python manage.py makemigrations core --name add_react_chat_usecase
python manage.py migrate
python manage.py makemigrations --check --dry-run
```

現在の最終 migration は `0004_datasource` です。追加の migration は `Agent.usecase_type` の `AlterField` で choices の変更を記録します。番号は他の変更と衝突しないよう自動生成に任せます。新しいテーブルや会話フィールドを追加する必要はありません。生成した migration も実装差分に含めます。

## 3. 手順 1: 実行を許可するツール

次の新規モジュールを作成します。価格は演習用の固定値です。

```text
backend/core/react_tools.py
```

```python
import json
import operator
from math import isfinite


PRODUCT_PRICES = {"ノート": 250, "ペン": 120, "消しゴム": 80}
OPERATIONS = {
    "add": operator.add,
    "subtract": operator.sub,
    "multiply": operator.mul,
    "divide": operator.truediv,
}


def get_product_price(product):
    if not isinstance(product, str) or product not in PRODUCT_PRICES:
        raise ValueError("登録されていない商品です。")
    return {"product": product, "price_yen": PRODUCT_PRICES[product]}


def calculate(operation, a, b):
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ValueError("対応していない演算です。")
    if any(type(value) not in (int, float) or not isfinite(value) for value in (a, b)):
        raise ValueError("a と b には有限の数値を指定してください。")
    result = OPERATIONS[operation](a, b)
    if not isfinite(result):
        raise ValueError("計算結果が数値の範囲を超えました。")
    return {"result": result}


TOOLS = [
    {
        "type": "function",
        "name": "get_product_price",
        "description": "商品の価格を円で取得する。登録商品はノート、ペン、消しゴム。",
        "parameters": {
            "type": "object",
            "properties": {"product": {"type": "string"}},
            "required": ["product"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "calculate",
        "description": "四則演算。subtract は a-b、divide は a/b。",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": list(OPERATIONS)},
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["operation", "a", "b"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

TOOL_FUNCTIONS = {
    "get_product_price": get_product_price,
    "calculate": calculate,
}


def execute_tool(name, arguments_json):
    if not isinstance(name, str) or name not in TOOL_FUNCTIONS:
        return {"error": "未登録のツールです。"}
    try:
        arguments = json.loads(arguments_json)
        if not isinstance(arguments, dict):
            raise ValueError("ツールの引数は JSON オブジェクトにしてください。")
        return TOOL_FUNCTIONS[name](**arguments)
    except (ValueError, TypeError, ArithmeticError) as exc:
        return {"error": str(exc)}
```

`TOOLS` はモデルに渡す説明、`TOOL_FUNCTIONS` はサーバーが実行できる関数の対応表です。モデルの出力を `eval` しません。`bool` は Python では `int` の派生型ですが、ここでは数値として許可しないため `type(value)` で確認します。JSON Schema があっても、Python 側の検証を省略しません。

**確認**: `execute_tool("get_product_price", '{"product":"ノート"}')` は価格を返し、未知のツール、不正 JSON、ゼロ除算は `error` を持つ辞書になります。

## 4. 手順 2: ReActRunner の反復処理

```text
backend/core/react_runner.py
```

```python
import json
from dataclasses import dataclass

from .react_tools import TOOLS, execute_tool


INSTRUCTIONS = (
    "あなたは演習用の商品について答えるアシスタントです。"
    "質問に必要なツールを選び、その結果から次の行動を決めてください。"
    "商品価格は必ず get_product_price で確認し、計算は必ず calculate を使ってください。"
    "ツールエラーが出たら引数を修正するか、回答できない理由を説明してください。"
    "必要な情報がそろったら、結果に基づいて日本語で簡潔に回答してください。"
)


class ReActError(RuntimeError):
    pass


class ReActLimitError(ReActError):
    pass


class ReActConfigurationError(ValueError):
    pass


@dataclass
class ReActResult:
    content: str
    usage: dict


class ReActRunner:
    def __init__(self, client, model, max_steps=8, system_prompt=""):
        if type(max_steps) is not int or not 1 <= max_steps <= 8:
            raise ReActConfigurationError("max_steps は 1–8 にしてください。")
        self.client = client
        self.model = model
        self.max_steps = max_steps
        self.instructions = INSTRUCTIONS + ("\n" + system_prompt if system_prompt else "")

    def run(self, messages):
        history = list(messages)
        usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        for step in range(self.max_steps):
            response = self.client.responses.create(
                model=self.model,
                instructions=self.instructions,
                input=list(history),
                tools=TOOLS,
                tool_choice="auto",
                parallel_tool_calls=False,
                reasoning={"effort": "none"},
                max_output_tokens=512,
            )
            if response.status != "completed":
                raise ReActError("モデルの応答が完了しませんでした。")

            for item in response.output:
                if item.type == "message":
                    for content in item.content:
                        if content.type == "refusal":
                            raise ReActError("モデルが回答を拒否しました。")

            for key in usage:
                value = getattr(response.usage, key, None)
                if type(value) is int:
                    usage[key] += value

            history.extend(response.output)
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                answer = response.output_text.strip()
                if not answer:
                    raise ReActError("最終回答が空でした。")
                return ReActResult(content=answer, usage=usage)

            for call in calls:
                result = execute_tool(call.name, call.arguments)
                history.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result, ensure_ascii=False, allow_nan=False),
                })

        raise ReActLimitError("最大ステップ数に達しました。")
```

参照例との主な違いは、`run(question)` を `run(messages)` にして、過去の会話を受け取れるようにした点です。Runner は Django を import しません。HTTP や保存処理を知らないため、偽クライアントだけで検証できます。

`response.output_text` だけではツール呼び出しを引き継げません。`response.output` 全体を追加し、各 `function_call` に同じ `call_id` の結果を返します。モデルの出力に推論用の項目が含まれても、勝手に取り除かず API へ引き継ぎ、ログや HTTP 応答には公開しません。

講義では参照例と同じ GPT-6 luna を使い、`reasoning={"effort": "none"}` も同じ設定にします。Agent の `system_prompt` は固定のツール利用指示と合わせて毎回渡します。設定を自由に変更できることは、権限のないツールを実行できることを意味しません。実行可能な処理はサーバー側の許可リストで制限します。

**確認**: 価格取得、掛け算、引き算、最終回答の 4 応答を順番に返す偽クライアントを用意します。3 回目のリクエストには、元の質問だけでなく価格取得と掛け算のための履歴が含まれるでしょうか。

## 5. 手順 3: 外部クライアントの生成

```text
backend/core/react_clients.py
```

```python
import os

from openai import OpenAI

from .react_runner import ReActConfigurationError


def open_react_client(llm):
    if not llm.is_active or llm.provider != "OPENAI":
        raise ReActConfigurationError("有効な OPENAI の LLM を指定してください。")
    if not llm.api_key or not llm.api_key.strip() or not llm.model.strip():
        raise ReActConfigurationError("API キーとモデル名を設定してください。")
    return OpenAI(
        api_key=llm.api_key,
        base_url=llm.base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1",
        timeout=30.0,
        max_retries=0,
    )
```

モデル名は SDK のクライアント生成時ではなく、Runner の `responses.create` へ渡します。

API キーは保存済みの `LLM` から取得します。HTTP の JSON で直接受け取りません。`with open_react_client(...) as client:` を使い、リクエスト後に接続を閉じます。参照スクリプトの環境変数ファイルは読み込みません。

本演習では `LLM.extra` や任意のリクエスト `options` を SDK へ展開しません。`max_steps` だけをアプリケーション側の設定として検証します。送信先、API キー、モデルは Agent の LLM 設定から決まり、`execute` の入力では変更できません。30 秒は個々の通信に対する timeout で、ReAct 全体の実行期限ではありません。SDK の再試行は無効にしていますが、Web サーバーやプロキシ側の待ち時間にも注意してください。

## 6. 手順 4: Usecase で会話を組み立てる

```text
backend/core/react_usecases.py
```

```python
from django.db import transaction

from .models import ChatSession, Message
from .react_runner import ReActConfigurationError


class ReActAgentUsecase:
    def __init__(self, agent, runner):
        if not agent.is_active or agent.usecase_type != "REACT_CHAT":
            raise ReActConfigurationError("有効な ReAct Agent を指定してください。")
        self.agent = agent
        self.runner = runner

    def run(self, user_text, session_uuid=None):
        if not isinstance(user_text, str) or not user_text.strip():
            raise ValueError("質問を入力してください。")
        user_text = user_text.strip()
        session = None
        messages = []
        if session_uuid is not None:
            session = ChatSession.objects.get(
                uuid=session_uuid, is_active=True, agent=self.agent,
            )
            if session.llm_id != self.agent.llm_id:
                raise ReActConfigurationError("会話と Agent の LLM 設定が異なります。")
            messages = [
                {"role": message.role, "content": message.content}
                for message in session.messages.filter(
                    role__in=["user", "assistant"],
                ).order_by("created_at", "id")
            ]
        messages.append({"role": "user", "content": user_text})

        result = self.runner.run(messages)

        with transaction.atomic():
            if session is None:
                session = ChatSession.objects.create(
                    agent=self.agent,
                    llm=self.agent.llm,
                )
            Message.objects.create(
                session=session,
                role="user",
                content=user_text,
            )
            assistant = Message.objects.create(
                session=session,
                role="assistant",
                content=result.content,
                usage=result.usage,
            )

        return {
            "agent_id": self.agent.id,
            "session_uuid": str(session.uuid),
            "result": {
                "message": {
                    "id": assistant.id,
                    "role": assistant.role,
                    "content": assistant.content,
                },
            },
            "usage": result.usage,
        }
```

### Usecase を読む順番

1. **対象を決める**: View が取得した Agent を受け取り、`REACT_CHAT` であることを確認します。LLM は `agent.llm` を使います。
2. **前提を守る**: UUID がある場合は `uuid`、`is_active`、`agent` で会話を取得します。他の Agent の会話や Agent のない会話は再利用しません。Agent の LLM を変更した場合も、以前の LLM の会話を暗黙に引き継ぎません。
3. **入力履歴を作る**: `session.messages` は `Message.session` の逆参照です。DB の会話へ今回の質問をメモリ上で追加します。
4. **実行を委譲する**: `runner.run` に渡すのは辞書のリストです。Usecase は SDK 固有の出力を扱いません。
5. **成功を保存する**: Runner が返った後で、初回なら会話を作成し、user と assistant を保存します。会話の新規作成を含めて、すべて成功するか、すべてロールバックされます。
6. **アプリケーションの結果を返す**: 既存の Agent execute と同じ構造の辞書を返します。`Response` や HTTP ステータスコードは返しません。

### なぜ user の保存を後にするのか

外部 API の失敗、回答拒否、ステップ上限では今回の対話を DB に残さない、という教材の方針です。質問を先に保存してから通信すると、失敗した user だけが次回の履歴に混ざります。

既存の `ChatInSessionUsecase.run` は外部通信を含めて `transaction.atomic` で囲んでいます。本例では通信中の長いトランザクションを避け、保存だけを囲みます。ただし、この変更だけで同時送信や再送時の二重実行を防げるわけではありません。

### 保存する履歴と保存しない履歴

| 対象 | 保存先 | 次回の扱い |
| --- | --- | --- |
| 利用者の質問と最終回答 | `Message.content` | user / assistant として読み直す |
| 成功した全ステップの usage | 最終回答の `Message.usage` | 表示や集計に利用できる |
| ツール要求、ツール結果、SDK の出力全体 | Runner の `history` のみ | リクエスト終了時に破棄する |
| モデルへの固定指示 | Runner の定数 | 問い合わせごとに `instructions` で渡す |
| Agent 固有の指示 | `Agent.system_prompt` | 固定指示へ加えて毎回渡し、Message には複製しない |

`Message` に `tool` role はありますが、本例では使いません。`call_id` などを落とした状態で tool のテキストだけを保存し、後から不完全な API 履歴を作ることを避けています。中断したツール処理の再開はできません。

## 7. 手順 5: Serializer で HTTP 入力を検証する

[serializers.py](../../../backend/core/serializers.py) に次のクラスを、既存 `AgentExecuteSerializer` より後へ追加します。BASIC_CHAT / RAG_CHAT の入力検証には影響させず、ReAct の分岐だけで利用します。

```python
class ReActExecuteSerializer(AgentExecuteSerializer):
    input = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        max_length=2000,
    )


class ReActSettingsSerializer(serializers.Serializer):
    max_steps = serializers.IntegerField(default=8, min_value=1, max_value=8)
```

`ReActExecuteSerializer` は `input` の検証と、既存の `session_uuid` / `options` を引き継ぎます。空白だけの質問や範囲外の `options.max_steps` は 400 になります。`ModelSerializer` と異なり、これらに `.save()` は不要です。保存は Usecase が担当します。

設定の優先順位は既存に合わせて `llm.extra < agent.config < request.options` とし、ReAct では `max_steps` だけを取り出して検証します。LLM / Agent の設定自体が不正なら 422、リクエストの上書きが不正なら 400 にします。それ以外の options は SDK へ転送しません。`retrieval_overrides` は RAG 用で、ReAct の演習では使用しません。

HTTP の検証とは別に Runner でも上限を確認しています。将来、管理コマンドなど HTTP 以外から実行されても、反復回数を無制限にしないためです。

## 8. 手順 6: View から Usecase を呼び出す

[views.py](../../../backend/core/views.py) の import に次を追加します。既存の import の置き換えではありません。

```python
from openai import APIError, APITimeoutError

from .react_clients import open_react_client
from .react_runner import ReActConfigurationError, ReActError, ReActRunner
from .react_usecases import ReActAgentUsecase
from .serializers import ReActExecuteSerializer, ReActSettingsSerializer
```

既存の `AgentViewSet.execute` に、次の分岐だけを挿入します。位置は `agent = self.get_object()` と inactive 判定の後、既存の `ser = AgentExecuteSerializer(...)` より前です。既存の options 結合、会話の作成、system メッセージ保存より後へ置くと、ReAct 失敗時に空の会話などが残ってしまいます。分岐後の BASIC_CHAT / RAG_CHAT は既存のままです。

```python
if agent.usecase_type == "REACT_CHAT":
    return self._execute_react(request, agent)
```

次の補助メソッドを `AgentViewSet` 内へ追加します。コードブロックでは先頭のインデントを省略しているので、クラス内では全体を 1 段下げます。新しい `@action` は付けません。

```python
def _execute_react(self, request, agent):
    serializer = ReActExecuteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    if not isinstance(agent.llm.extra, dict) or not isinstance(agent.config, dict):
        return Response({"detail": "Invalid ReAct configuration"}, status=422)
    defaults = ReActSettingsSerializer(data={**agent.llm.extra, **agent.config})
    if not defaults.is_valid():
        return Response({"detail": "Invalid ReAct configuration"}, status=422)
    settings = ReActSettingsSerializer(data={
        **defaults.validated_data,
        **serializer.validated_data.get("options", {}),
    })
    settings.is_valid(raise_exception=True)

    try:
        with open_react_client(agent.llm) as client:
            runner = ReActRunner(
                client=client,
                model=agent.llm.model,
                max_steps=settings.validated_data["max_steps"],
                system_prompt=agent.system_prompt or "",
            )
            usecase = ReActAgentUsecase(agent, runner)
            result = usecase.run(
                serializer.validated_data["input"],
                session_uuid=serializer.validated_data.get("session_uuid"),
            )
    except ChatSession.DoesNotExist:
        return Response({"detail": "Session not found"}, status=404)
    except ReActConfigurationError as exc:
        return Response({"detail": str(exc)}, status=422)
    except APITimeoutError:
        return Response({"detail": "LLM request timed out"}, status=504)
    except (APIError, ReActError):
        return Response({"detail": "ReAct execution failed"}, status=502)

    return Response(result, status=200)
```

`execute` の `self.get_object()` は既存の active Agent QuerySet と DRF のオブジェクト権限確認を使い、存在しない Agent を 404 にします。会話の UUID と Agent の対応は Usecase が確認し、`ChatSession.DoesNotExist` を View が 404 へ変換します。DB 保存の予期しない障害まで一括で捕まえて 200 にしないでください。

外部 SDK の例外本文は、そのまま利用者へ返しません。認証情報やプロバイダーの詳細を含む可能性があるためです。タイムアウトは `APIError` の派生型なので、先に捕まえます。

この View は「入力の検証 → 依存する実装の準備 → Usecase 呼び出し → HTTP への変換」を行います。反復処理や `Message.objects.create` を View へ移さないことがポイントです。

## 9. テスト: 外部 API と DB を分けて確認する

最初から実 LLM だけで試すと、失敗が実装、モデル選択、利用枠、通信のどれに由来するか分かりません。次の 3 層に分けます。

| 対象 | 実物を使うもの | 置き換えるもの |
| --- | --- | --- |
| Runner | ツール、JSON 処理、履歴の組み立て | SDK の応答 |
| Usecase | Django ORM とテスト DB | Runner |
| API | Router、View、Serializer、Usecase、テスト DB | SDK クライアントの生成と Runner |

テストは完成例です。まず入力と期待結果を読み、どの行で失敗するはずか予想してから実行してください。Fake が予定した応答を返すことは、実際のモデルが同じツールを選ぶ保証にはなりません。

テストでは外部 API を必ず置き換えます。ソースを読み取り専用で扱う検証では、資料のコードと Model choices の変更をメモリ内に反映し、既存 Router とインメモリ SQLite を使って実行できます。これは通常の演習環境での migration 適用や、GPT-6 luna の実機確認を代替しません。

教材更新時には、Python 3.12.16、Django 5.2.19、OpenAI SDK 2.54.0 の一時コンテナで、下記の新しいテスト例 23 件と既存の Agent・通常チャット・認証テスト 22 件、計 45 件の成功を確認しました。既存 `execute` への分岐挿入もメモリ内で行い、ソースは読み取り専用、外部ネットワーク接続は無効です。migration 自動検出では `Agent.usecase_type` の `AlterField` のみになることを確認しています。実 DB への新しい migration の適用、配布キーによる実 API 通信、ブラウザー操作は未検証です。授業前に講師が実機確認を行ってください。

### 9-1. Runner とツール

```text
backend/core/tests/test_react_runner.py
```

```python
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from core.react_runner import (
    ReActConfigurationError,
    ReActError,
    ReActLimitError,
    ReActRunner,
)
from core.react_tools import execute_tool


def tool_call(name, arguments, call_id):
    return SimpleNamespace(
        type="function_call",
        name=name,
        arguments=json.dumps(arguments, ensure_ascii=False),
        call_id=call_id,
    )


def response(output=None, text="", status="completed"):
    return SimpleNamespace(
        status=status,
        output=output or [],
        output_text=text,
        usage=SimpleNamespace(input_tokens=2, output_tokens=1, total_tokens=3),
    )


class ReActRunnerTests(TestCase):
    def test_four_steps_keep_outputs_and_call_ids(self):
        client = Mock()
        marker = SimpleNamespace(type="reasoning")
        client.responses.create.side_effect = [
            response([
                marker,
                tool_call("get_product_price", {"product": "ノート"}, "price-1"),
            ]),
            response([tool_call(
                "calculate", {"operation": "multiply", "a": 250, "b": 3}, "math-1",
            )]),
            response([tool_call(
                "calculate", {"operation": "subtract", "a": 1000, "b": 750}, "math-2",
            )]),
            response(text="お釣りは250円です。"),
        ]
        messages = [{"role": "user", "content": "ノート3冊のお釣りは？"}]

        result = ReActRunner(client, "mock-model", max_steps=4).run(messages)

        self.assertEqual(result.content, "お釣りは250円です。")
        self.assertEqual(result.usage["total_tokens"], 12)
        self.assertEqual(len(messages), 1)
        self.assertEqual(client.responses.create.call_count, 4)
        last_input = client.responses.create.call_args.kwargs["input"]
        self.assertIs(last_input[1], marker)
        outputs = [
            item for item in last_input
            if isinstance(item, dict) and item.get("type") == "function_call_output"
        ]
        self.assertEqual(
            [item["call_id"] for item in outputs], ["price-1", "math-1", "math-2"],
        )
        self.assertEqual(json.loads(outputs[-1]["output"]), {"result": 250})

    def test_tool_error_is_returned_as_observation(self):
        client = Mock()
        client.responses.create.side_effect = [
            response([tool_call("get_product_price", {"product": "未知の商品"}, "bad")]),
            response([tool_call("get_product_price", {"product": "ペン"}, "good")]),
            response(text="ペンは120円です。"),
        ]

        result = ReActRunner(client, "mock-model").run([
            {"role": "user", "content": "商品の価格は？"},
        ])

        second_input = client.responses.create.call_args_list[1].kwargs["input"]
        self.assertIn("error", json.loads(second_input[-1]["output"]))
        self.assertEqual(result.content, "ペンは120円です。")

    def test_max_steps_stops_without_an_extra_request(self):
        client = Mock()
        client.responses.create.return_value = response([
            tool_call("get_product_price", {"product": "ノート"}, "price-1"),
        ])
        with self.assertRaises(ReActLimitError):
            ReActRunner(client, "mock-model", max_steps=1).run([
                {"role": "user", "content": "価格は？"},
            ])
        self.assertEqual(client.responses.create.call_count, 1)

    def test_incomplete_empty_and_refused_responses_fail(self):
        refusal = SimpleNamespace(
            type="message",
            content=[SimpleNamespace(type="refusal", refusal="拒否の例")],
        )
        for invalid in [
            response(status="incomplete"),
            response(text="  "),
            response(output=[refusal]),
        ]:
            with self.subTest(response=invalid):
                client = Mock()
                client.responses.create.return_value = invalid
                with self.assertRaises(ReActError):
                    ReActRunner(client, "mock-model").run([])

    def test_step_limit_is_validated_without_http(self):
        for limit in [0, 9, True]:
            with self.subTest(limit=limit):
                with self.assertRaises(ReActConfigurationError):
                    ReActRunner(Mock(), "mock-model", max_steps=limit)

    def test_tools_reject_invalid_inputs(self):
        cases = [
            ("unknown", "{}"),
            ("calculate", "not-json"),
            ("calculate", "[]"),
            ("calculate", '{"operation":"divide","a":1,"b":0}'),
            ("calculate", '{"operation":"add","a":true,"b":1}'),
            ("calculate", '{"operation":"add","a":1e999,"b":1}'),
            ("calculate", '{"operation":[],"a":1,"b":1}'),
            ("get_product_price", '{"product":"ノート","extra":1}'),
        ]
        for name, arguments in cases:
            with self.subTest(name=name, arguments=arguments):
                self.assertIn("error", execute_tool(name, arguments))
```

### 9-2. Usecase の保存と会話継続

```text
backend/core/tests/test_react_usecase.py
```

```python
from unittest.mock import Mock, patch

from django.test import TestCase

from core.models import Agent, ChatSession, LLM, Message
from core.react_runner import ReActLimitError, ReActResult
from core.react_usecases import ReActAgentUsecase


class ReActUsecaseTests(TestCase):
    def setUp(self):
        self.llm = LLM.objects.create(
            name="GPT-6 luna", provider="OPENAI", model="gpt-6-luna",
        )
        self.agent = Agent.objects.create(
            name="ReAct", usecase_type="REACT_CHAT", llm=self.llm,
        )
        self.session = ChatSession.objects.create(llm=self.llm, agent=self.agent)
        self.runner = Mock()
        self.runner.run.return_value = ReActResult(
            content="お釣りは250円です。", usage={"total_tokens": 12},
        )

    def test_success_creates_session_user_and_assistant(self):
        result = ReActAgentUsecase(self.agent, self.runner).run("質問")
        session = ChatSession.objects.get(uuid=result["session_uuid"])

        self.assertEqual(result["agent_id"], self.agent.id)
        self.assertEqual(session.agent_id, self.agent.id)
        self.assertEqual(session.llm_id, self.llm.id)
        self.assertEqual(result["result"]["message"]["content"], "お釣りは250円です。")
        self.assertEqual(
            list(session.messages.values_list("role", flat=True)),
            ["user", "assistant"],
        )
        self.assertEqual(session.messages.last().usage, {"total_tokens": 12})

    def test_next_turn_receives_previous_messages(self):
        usecase = ReActAgentUsecase(self.agent, self.runner)
        first = usecase.run("最初の質問")
        second = usecase.run("ではペン2本なら？", session_uuid=first["session_uuid"])

        received = self.runner.run.call_args.args[0]
        self.assertEqual([item["role"] for item in received], [
            "user", "assistant", "user",
        ])
        self.assertEqual(received[0]["content"], "最初の質問")
        self.assertEqual(received[-1]["content"], "ではペン2本なら？")
        self.assertEqual(first["session_uuid"], second["session_uuid"])
        session = ChatSession.objects.get(uuid=first["session_uuid"])
        self.assertEqual(session.messages.count(), 4)
        self.assertEqual(session.messages.filter(role="system").count(), 0)

    def test_runner_failure_leaves_existing_history_unchanged(self):
        Message.objects.create(session=self.session, role="user", content="過去の質問")
        previous_ids = list(self.session.messages.values_list("id", flat=True))
        self.runner.run.side_effect = ReActLimitError("上限")

        with self.assertRaises(ReActLimitError):
            ReActAgentUsecase(self.agent, self.runner).run(
                "新しい質問", session_uuid=self.session.uuid,
            )

        self.assertEqual(
            list(self.session.messages.values_list("id", flat=True)), previous_ids,
        )

    def test_first_runner_failure_does_not_create_empty_session(self):
        previous_count = self.agent.sessions.count()
        self.runner.run.side_effect = ReActLimitError("上限")
        with self.assertRaises(ReActLimitError):
            ReActAgentUsecase(self.agent, self.runner).run("質問")
        self.assertEqual(self.agent.sessions.count(), previous_count)
        self.assertEqual(Message.objects.count(), 0)

    def test_assistant_save_failure_rolls_back_new_session_and_user(self):
        previous_count = self.agent.sessions.count()
        original_create = Message.objects.create

        def persist(**fields):
            if fields["role"] == "assistant":
                raise RuntimeError("保存失敗の再現")
            return original_create(**fields)

        with patch("core.react_usecases.Message.objects.create", side_effect=persist):
            with self.assertRaises(RuntimeError):
                ReActAgentUsecase(self.agent, self.runner).run("質問")

        self.assertEqual(self.agent.sessions.count(), previous_count)
        self.assertEqual(Message.objects.count(), 0)

    def test_assistant_save_failure_rolls_back_existing_session_user(self):
        original_create = Message.objects.create

        def persist(**fields):
            if fields["role"] == "assistant":
                raise RuntimeError("保存失敗の再現")
            return original_create(**fields)

        with patch("core.react_usecases.Message.objects.create", side_effect=persist):
            with self.assertRaises(RuntimeError):
                ReActAgentUsecase(self.agent, self.runner).run(
                    "質問", session_uuid=self.session.uuid,
                )
        self.assertEqual(self.session.messages.count(), 0)

    def test_foreign_session_is_not_passed_to_runner(self):
        other_agent = Agent.objects.create(
            name="Other", usecase_type="REACT_CHAT", llm=self.llm,
        )
        other_session = ChatSession.objects.create(llm=self.llm, agent=other_agent)
        with self.assertRaises(ChatSession.DoesNotExist):
            ReActAgentUsecase(self.agent, self.runner).run(
                "質問", session_uuid=other_session.uuid,
            )
        self.runner.run.assert_not_called()
```

LLM は注入した Runner に置き換えますが、ORM は置き換えていません。`TestCase` のテスト用 DB で、本当に 2 件保存されることとロールバックを確認します。テストに使用する `LLM` のキーは不要です。このテストではクライアント生成を呼ばないためであり、実 API にキーが不要という意味ではありません。

### 9-3. HTTP の入口

```text
backend/core/tests/test_react_api.py
```

```python
from unittest.mock import patch
from uuid import uuid4

import httpx
from django.contrib.auth import get_user_model
from django.test import TestCase
from openai import APIConnectionError, APITimeoutError
from rest_framework.test import APIClient

from core.models import Agent, ChatSession, LLM, Message
from core.react_runner import ReActError, ReActLimitError, ReActResult


class ReActApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(get_user_model().objects.create_user("student"))
        self.llm = LLM.objects.create(
            name="GPT-6 luna", provider="OPENAI", model="gpt-6-luna", api_key="unused",
            extra={"max_steps": 2},
        )
        self.agent = Agent.objects.create(
            name="ReAct", usecase_type="REACT_CHAT", llm=self.llm,
            config={"max_steps": 4}, system_prompt="講義用の商品について回答する。",
        )
        self.url = f"/api/agents/{self.agent.id}/execute/"

    def test_create_accepts_react_chat_and_rejects_custom(self):
        body = {"name": "New", "usecase_type": "REACT_CHAT", "llm": self.llm.id}
        result = self.client.post("/api/agents/", body, format="json")
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.data["usecase_type"], "REACT_CHAT")
        body["usecase_type"] = "CUSTOM"
        result = self.client.post("/api/agents/", body, format="json")
        self.assertEqual(result.status_code, 400)

    def test_success_uses_usecase_and_returns_message(self):
        with (
            patch("core.views.open_react_client"),
            patch("core.views.ReActRunner") as runner_class,
        ):
            runner_class.return_value.run.return_value = ReActResult(
                content="250円です。", usage={"total_tokens": 12},
            )
            result = self.client.post(self.url, {"input": "質問"}, format="json")

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["agent_id"], self.agent.id)
        self.assertEqual(result.data["result"]["message"]["content"], "250円です。")
        session = ChatSession.objects.get(uuid=result.data["session_uuid"])
        self.assertEqual(session.agent_id, self.agent.id)
        self.assertEqual(session.messages.count(), 2)
        self.assertEqual(runner_class.call_args.kwargs["model"], "gpt-6-luna")
        self.assertEqual(
            runner_class.call_args.kwargs["system_prompt"], self.agent.system_prompt,
        )

    def test_invalid_input_returns_400_before_client_creation(self):
        for body in [
            {}, {"input": "  "}, {"input": "x" * 2001},
            {"input": "質問", "session_uuid": "invalid"},
            {"input": "質問", "options": {"max_steps": 0}},
            {"input": "質問", "options": {"max_steps": 9}},
            {"input": "質問", "options": {"max_steps": "invalid"}},
        ]:
            with self.subTest(body=body):
                with patch("core.views.open_react_client") as factory:
                    result = self.client.post(self.url, body, format="json")
                self.assertEqual(result.status_code, 400)
                factory.assert_not_called()
        self.assertEqual(self.agent.sessions.count(), 0)

    def test_missing_inactive_and_foreign_sessions_return_404(self):
        inactive = ChatSession.objects.create(
            agent=self.agent, llm=self.llm, is_active=False,
        )
        other_agent = Agent.objects.create(
            name="Other", usecase_type="REACT_CHAT", llm=self.llm,
        )
        foreign = ChatSession.objects.create(agent=other_agent, llm=self.llm)
        standalone = ChatSession.objects.create(llm=self.llm)
        for session_uuid in [uuid4(), inactive.uuid, foreign.uuid, standalone.uuid]:
            with self.subTest(session_uuid=session_uuid):
                with (
                    patch("core.views.open_react_client"),
                    patch("core.views.ReActRunner") as runner_class,
                ):
                    result = self.client.post(
                        self.url, {"input": "質問", "session_uuid": str(session_uuid)},
                        format="json",
                    )
                self.assertEqual(result.status_code, 404)
                runner_class.return_value.run.assert_not_called()
        self.assertEqual(Message.objects.count(), 0)

    def test_missing_and_inactive_agents_return_404(self):
        self.agent.is_active = False
        self.agent.save(update_fields=["is_active"])
        for agent_id in [self.agent.id, self.agent.id + 1000]:
            with self.subTest(agent_id=agent_id):
                with patch("core.views.open_react_client") as factory:
                    result = self.client.post(
                        f"/api/agents/{agent_id}/execute/", {"input": "質問"},
                        format="json",
                    )
                self.assertEqual(result.status_code, 404)
                factory.assert_not_called()

    def test_invalid_llm_returns_422(self):
        for provider, active, key in [
            ("OLLAMA", True, "unused"),
            ("OPENAI", False, "unused"),
            ("OPENAI", True, ""),
        ]:
            with self.subTest(provider=provider, active=active, key_present=bool(key)):
                self.llm.provider = provider
                self.llm.is_active = active
                self.llm.api_key = key
                self.llm.save(update_fields=["provider", "is_active", "api_key"])
                result = self.client.post(self.url, {"input": "質問"}, format="json")
                self.assertEqual(result.status_code, 422)
                self.assertEqual(self.agent.sessions.count(), 0)

    def test_options_follow_existing_merge_order(self):
        for options, expected_steps in [({}, 4), ({"max_steps": 6}, 6)]:
            with self.subTest(options=options):
                with (
                    patch("core.views.open_react_client"),
                    patch("core.views.ReActRunner") as runner_class,
                ):
                    runner_class.return_value.run.return_value = ReActResult("回答", {})
                    result = self.client.post(
                        self.url, {"input": "質問", "options": options}, format="json",
                    )
                self.assertEqual(result.status_code, 200)
                self.assertEqual(
                    runner_class.call_args.kwargs["max_steps"], expected_steps,
                )

    def test_invalid_defaults_return_422(self):
        for config in [[], {"max_steps": 0}]:
            with self.subTest(config=config):
                self.agent.config = config
                self.agent.save(update_fields=["config"])
                with patch("core.views.open_react_client") as factory:
                    result = self.client.post(self.url, {"input": "質問"}, format="json")
                self.assertEqual(result.status_code, 422)
                factory.assert_not_called()

    def test_changed_agent_llm_does_not_reuse_old_llm_session(self):
        other_llm = LLM.objects.create(
            name="Old", provider="OPENAI", model="old-model",
        )
        session = ChatSession.objects.create(
            agent=self.agent, llm=other_llm,
        )
        with patch("core.views.open_react_client"):
            result = self.client.post(
                self.url, {"input": "質問", "session_uuid": str(session.uuid)},
                format="json",
            )
        self.assertEqual(result.status_code, 422)
        self.assertEqual(session.messages.count(), 0)

    def test_upstream_errors_are_mapped_without_saving(self):
        request = httpx.Request("POST", "https://example.invalid/v1/responses")
        for error, expected_status in [
            (ReActLimitError("上限"), 502),
            (ReActError("空回答"), 502),
            (APIConnectionError(request=request), 502),
            (APITimeoutError(request=request), 504),
        ]:
            with self.subTest(error=type(error).__name__):
                with (
                    patch("core.views.open_react_client"),
                    patch("core.views.ReActRunner") as runner_class,
                ):
                    runner_class.return_value.run.side_effect = error
                    result = self.client.post(self.url, {"input": "質問"}, format="json")
                self.assertEqual(result.status_code, expected_status)
                self.assertEqual(self.agent.sessions.count(), 0)
                self.assertEqual(Message.objects.count(), 0)
```

`force_authenticate` は認証自体の検証を省略します。このテストだけでログイン、期限切れ、CSRF が正しいとは判断しません。既存の [認証テスト](../../../backend/core/tests/test_auth_api.py) と役割を分けます。`httpx` は OpenAI SDK の依存であり、上の例では例外に添付するリクエスト情報を作るだけです。

### 9-4. 実行順と観察

以下は演習の実装とテストを追加した後のコマンドです。教材だけがある状態では、新しいテストラベルはまだ存在しません。リポジトリルートで実行します。

```bash
bash scripts/test-backend.sh core.tests.test_react_runner
bash scripts/test-backend.sh core.tests.test_react_usecase
bash scripts/test-backend.sh core.tests.test_react_api
bash scripts/test-backend.sh core.tests.test_chat_usecase core.tests.test_agent_api core.tests.test_auth_api
```

[テストスクリプト](../../../scripts/test-backend.sh) は一時 backend コンテナで [SQLite の設定](../../../backend/lecture_system/test_settings.py) を使います。PostgreSQL や Ollama の起動、実 LLM の API キーは不要です。新しい依存を含むイメージは準備しておきます。

VS Code で停止する場合は [既存のデバッグ手順](orm-database-debug-workshop.md) を利用し、テストラベルを上記へ変更します。次の位置で観察します。

1. Serializer の検証直後: `validated_data` と既定のステップ上限。
2. `runner.run(messages)` の直前: 過去の会話と今回の質問の並び。
3. ツール実行の直前: ツール名、引数の型、`call_id`。
4. 2 回目以降の `responses.create` の直前: 前回の要求と観測結果の対応。
5. 保存用 `transaction.atomic` の直前と直後: Message 件数が 0 件から 2 件になること。

テストで使う固定の質問は観察して構いませんが、実利用者の会話、API キー、SDK クライアントの認証ヘッダーをスクリーンショットやログに含めないでください。

## 10. 実機演習: GPT-6 luna を Agent execute から利用する

この節は講義で配布する API キーを使う実機確認です。外部 API 通信と料金が発生し得るため、キーの使用範囲と利用枠を確認してから進めます。

1. 準備で登録した LLM が表示名 `GPT-6 luna`、model `gpt-6-luna`、provider `OPENAI` であることと、配布キーを設定したことを確認します。キーを再表示・撮影する必要はありません。
2. migration を適用し、backend を再起動します。Docker を使う場合は SDK を含むイメージへ更新します。応答待ちが Web サーバーの期限を超える場合は、開発環境側の制限も確認します。
3. アプリケーションへ通常の手順でログインします。会話の作成 API は先に呼ばず、Agent の最初の実行に任せます。
4. 同じオリジンのブラウザー開発者コンソールで次の例を実行します。`llmId` は登録した GPT-6 luna の ID に変更します。新しい Agent の作成に API キーを含めません。

```javascript
const llmId = 1;
const csrfResponse = await fetch('/api/csrf/', { credentials: 'same-origin' });
if (!csrfResponse.ok) throw new Error(`CSRF: ${csrfResponse.status}`);
const { csrftoken } = await csrfResponse.json();

async function postJson(url, body) {
  const result = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrftoken,
    },
    body: JSON.stringify(body),
  });
  if (!result.ok) throw new Error(`HTTP ${result.status}`);
  return result.json();
}

const agent = await postJson('/api/agents/', {
    name: 'Stationery ReAct',
    usecase_type: 'REACT_CHAT',
  llm: llmId,
    system_prompt: '文房具について日本語で簡潔に回答してください。',
    config: { max_steps: 8 },
    tools: {},
});
const first = await postJson(`/api/agents/${agent.id}/execute/`, {
    input: 'ノートを3冊買って1000円を支払うと、お釣りはいくらですか？',
    options: { max_steps: 8 },
});
console.log(first.result.message.content);

const second = await postJson(`/api/agents/${agent.id}/execute/`, {
    input: 'ではペン2本を買って500円を支払う場合は？',
    session_uuid: first.session_uuid,
    options: { max_steps: 8 },
});
console.log(second.result.message.content);
```

最初の答えは 250 円、次の答えは 260 円です。表現やツールの選択順はモデルによって変わります。ツールの出力を使わずに答えた場合は、数字が合っていても講義の観察対象としては不十分です。テスト、デバッガー、または秘密情報を含まないツール名と成功・失敗だけの一時的な計測で、実行経路を確認します。

`execute` の ReAct 分岐では 1 対話につき 2 件の Message を保存します。返された `first.session_uuid` を使い、既存のメッセージ一覧 API で user / assistant が 4 件あることを確認します。API キーや CSRF トークンはコンソール出力へ追加しません。

## 11. よくある失敗と切り分け

| 症状 | 確認箇所 |
| --- | --- |
| `openai` を import できない | backend の依存追加、イメージ再ビルド、VS Code の Python 選択 |
| Agent 作成時に `REACT_CHAT` が拒否される | Model choices と作成・更新 Serializer の両方を更新したか |
| `execute` が 404 | Agent が有効か、指定 UUID の会話が有効か、その Agent に属するか |
| HTTP 400 | `input` の空白・長さと `options.max_steps`。モデルへ問い合わせる前のエラーか |
| HTTP 422 | LLM の provider / active / API キー、Agent 設定、会話と Agent の LLM の一致 |
| ツール引数が不正 | 実行関数が `error` を返すか、次の問い合わせへ観測結果を追加したか |
| tool result の対応エラー | 出力全体を残しているか、要求と結果の `call_id` が一致するか |
| HTTP 502 | 上限、空回答、拒否、モデル非対応、利用枠、接続失敗をテストで分離する |
| HTTP 504 | SDK の通信待ち。無制限の再試行で隠さない |
| 対話を継続できない | 同じ UUID か、DB 履歴を毎回読み直しているか |
| テストだけ実 API へ接続する | patch 先が定義元ではなく、利用先の `core.views` になっているか |

## 12. 完了条件と本番運用との差

- 反復処理を View へ置かず、Usecase が会話取得と保存を管理している。
- 価格取得と四則演算の許可リストを守り、引数をサーバー側で検証している。
- `call_id` と出力全体を引き継ぎ、上限・拒否・空回答で停止できる。
- 成功時は user と assistant が 2 件増え、Runner 失敗時と保存失敗時は増えない。
- 同じ UUID の 2 対話目に過去の user / assistant が渡る。
- 新しい Route を作らず、`REACT_CHAT` を既存の `execute` で選択し、既存の応答形式を維持している。
- 配布キーで登録した GPT-6 luna を Agent の `llm` に指定し、実機で 2 回対話できる。
- 別 Agent の UUID を拒否し、初回失敗時に空の会話も残さない。
- 既存の通常チャット、Agent、認証のテストを壊していない。
- 秘密情報やモデル内部の推論過程を応答、ログ、提出物へ追加していない。

この実装は **逐次送信する演習用** です。会話のユーザー所有権、同時送信の直列化、冪等キー、失敗を含む課金の記録、履歴のトークン予算、全体の実行期限、レート制限、許可された送信先の管理は未実装です。API 入力の 2,000 文字制限は、蓄積した履歴全体の制限にはなりません。

`ChatSession` にはユーザー所有者がなく、現在の View は会話をユーザー別に絞りません。実データを扱う公開 API にする前に、所有権と権限を設計してください。任意の `base_url` を登録できる権限にも注意が必要です。また、DB のロールバックは外部サービスで起きた副作用を取り消しません。本演習が読み取りと計算だけのツールを使う理由です。

Agent の `execute` への統合は発展課題ではなく本演習の必修範囲です。Model choices、Serializer、migration、View の分岐、API 仕様を一緒に更新したことを確認します。`CUSTOM` は Model に存在しますが、便宜的に流用しません。BASIC_CHAT / RAG_CHAT も Usecase 化する作業は [講義の発展課題](react-agent-backend-lecture.md) として切り分けます。

