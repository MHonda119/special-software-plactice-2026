# OpenAI API 基礎演習

Python から OpenAI API を直接呼び出す演習です。講義システムの起動、Docker、Django、データベースは不要です。Python 3.11 以上、インターネット接続、対象モデルを利用できる OpenAI API キーを用意してください。API の呼び出しには利用料金が発生します。

## 準備

リポジトリのルートから、演習専用の仮想環境を作ります。

```bash
cd scripts/api_basics
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Windows PowerShell では `python3` の代わりに `python`、仮想環境の有効化には `.\.venv\Scripts\Activate.ps1`、コピーには `Copy-Item .env.example .env` を使います。

`.env` の `OPENAI_API_KEY` を自分のキーに書き換えてください。すでに `.env` がある場合はコピーせず、既存の設定を編集します。

```dotenv
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-6-luna
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

キーはソースコードに書き込みません。`.env` は Git の管理対象外です。環境変数での指定もでき、同名の環境変数がある場合は `.env` より優先します。`common.py` はこのディレクトリの `.env` を読み込むため、実行時の作業ディレクトリに依存せず、講義システムの `.env` を読み込みません。

GPT の既定モデルは `gpt-6-luna`、Embedding の既定モデルは `text-embedding-3-small` です。Embedding は `text-embedding-3-large` に変更することもできます。GPT の演習では `reasoning.effort="none"`（Chat Completions では `reasoning_effort="none"`）を使います。`OPENAI_MODEL` を変更する場合、Project の利用許可に加え、そのモデルが演習のパラメータをサポートすることも確認してください。

## 実行

上記の仮想環境を有効にした状態で実行します。

```bash
python 01_helloworld.py
python 02_chat_history.py
python 03_embedding_and_tokens.py
python 04_output_control.py
python 05_rag_basics_tohokubert.py
python 06_react_agent.py
```

| ファイル | 内容 | 確認する出力 |
| --- | --- | --- |
| `01_helloworld.py` | Responses API によるテキスト生成 | 短い挨拶、トークン使用量 |
| `02_chat_history.py` | Chat Completions API に会話履歴を渡す | 文脈を引き継いだ回答、トークン使用量 |
| `03_embedding_and_tokens.py` | 3つの文章をまとめてベクトル化 | ベクトル数3、次元数、入力トークン使用量 |
| `04_output_control.py` | 厳密な JSON Schema、温度と出力上限 | JSON、温度ごとの生成結果 |
| `05_rag_basics_tohokubert.py` | 例示文書の検索結果を使って回答する RAG | 類似度と取得文書、残り有給日数についての回答 |
| `06_react_agent.py` | ツールを選び、結果を見て次の行動を決める ReAct エージェント | Action、Observation、最終回答 |

Embedding の既定次元数は `text-embedding-3-small` が1536、`text-embedding-3-large` が3072です。生成結果や使用トークン数は実行ごとに変わります。

`04_output_control.py` は構造化出力を1回、温度0・1・2で各3回生成します。短時間で動作確認する場合は、次のように各温度の生成を1回にできます。温度0でも同一の出力が保証されるわけではありません。

```bash
python 04_output_control.py --repeats 1
```

`05_rag_basics_tohokubert.py` は既定で OpenAI Embeddings を使用します。文書と質問を同じモデルでベクトル化し、コサイン類似度で検索します。サンプルの質問も変更できます。

```bash
python 05_rag_basics_tohokubert.py --question "東京オフィスの受付は何階ですか？"
```

## ReAct エージェント

`06_react_agent.py` は、ReAct の「判断 → 実行 → 観測」のループを Responses API の Function Calling で実装した例です。`ReActAgent.run()` がモデルへの問い合わせを繰り返し、モデルが選んだ Python 関数を実行します。ツール結果を会話履歴に追加し、次の問い合わせでモデルに渡します。

ツールは同じファイル内にあり、追加ライブラリや外部サービスは不要です。

| ツール | 機能 |
| --- | --- |
| `get_product_price(product)` | 架空の商品価格を取得（ノート250円、ペン120円、消しゴム80円） |
| `calculate(operation, a, b)` | 2つの数値の加算・減算・乗算・除算 |

既定の質問は「ノートを3冊買って1000円を支払うと、お釣りはいくらですか？」です。モデルが価格の取得と計算を行い、最終的にお釣り250円と回答します。実行中は、呼び出したツールが `[Action]`、その結果が `[Observation]` として表示されます。

```bash
python 06_react_agent.py
python 06_react_agent.py --question "ペンを2本と消しゴムを1個買うと合計はいくらですか？"
python 06_react_agent.py --max-steps 6
```

`--max-steps` は最終回答を含むモデルへの問い合わせ回数の上限で、既定値は8です。上限内に完了しない場合はエラーで終了します。未登録の商品やゼロ除算などのツールエラーも観測結果としてモデルに返し、引数の修正や説明に使います。実行する関数は `TOOL_FUNCTIONS` に登録したものに限り、計算に `eval` は使いません。

## 任意: TohokuBERT による埋め込み

ローカルの日本語 BERT と OpenAI Embeddings を比較する場合だけ、追加の依存関係をインストールします。初回は Hugging Face から `cl-tohoku/bert-base-japanese` をダウンロードするため、追加の通信時間とディスク容量が必要です。回答の生成には引き続き OpenAI API を使います。

```bash
python -m pip install -r requirements-tohokubert.txt
python 05_rag_basics_tohokubert.py --embedding-backend tohokubert
```

この BERT モデルのトークナイザーは `fugashi` と `ipadic` を使います。文書と質問の両方に同じ BERT と、パディングを除外した平均プーリングを使用します。汎用 BERT の平均プーリングは検索専用に学習されたモデルではないため、OpenAI Embeddings と検索順位が異なる場合があります。

## 動作確認結果（2026-10-05）

講義システムを起動せず、独立した仮想環境（Python 3.11.9、openai 3.24.0、python-dotenv 1.2.4）で、提供された API キーを環境変数経由で渡して実行しました。キーはソースコード・設定ファイルに保存していません。

| 演習 | 実 API での確認結果 |
| --- | --- |
| 01 | `gpt-6-luna` が挨拶と使用トークン数を返し、正常終了 |
| 02 | 会話履歴を踏まえた日本語の回答を返し、正常終了 |
| 03 | small は1536次元、large は3072次元で、それぞれ3つのベクトルを取得 |
| 04 | JSON Schema に一致する出力と、温度0・1・2で各3回の生成に成功 |
| 05 | 該当文書を検索し、「残り有給日数は5日です」と回答 |
| 06 | 価格取得 → 乗算 → 減算の3回のツール実行を経て、4回目のモデル応答で「お釣り250円」と回答 |

リポジトリのルート、演習ディレクトリ、別の作業ディレクトリからの実行も確認しました。構文確認、設定の読み込み、API を使わない疑似応答による異常系の確認も実施しています。任意の TohokuBERT 経路は、検証環境のディスク容量制約により実モデルでの実行を確認していません。追加依存がない場合のインストール案内は確認しています。

## エラーが出た場合

- `OPENAI_API_KEY を…設定してください`: `.env.example` を参考にキーを設定してください。
- `ModuleNotFoundError`: 仮想環境が有効か確認し、同じ `python` で `python -m pip install -r requirements.txt` を実行してください。
- HTTP 401: キーが有効か確認してください。
- HTTP 403、またはモデルにアクセスできない旨のエラー: キーが属する Project のモデル利用許可を確認してください。
- HTTP 429: 利用枠、残高、リクエスト頻度を確認してください。

モデルの権限制限は OpenAI の Project 側で管理します。認証・通信・利用枠のエラーだけでは、モデルが禁止されているかを判定できません。

## 公式資料

- [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)
- [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Embeddings](https://developers.openai.com/api/docs/guides/embeddings)
- [Function calling](https://developers.openai.com/api/docs/guides/function-calling)
