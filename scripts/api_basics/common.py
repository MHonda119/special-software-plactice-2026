import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# [注1] .env は KEY=VALUE の形式で設定を書くローカルファイル。
# __file__ はこの common.py の場所を表し、with_name で隣の .env を指定する。
# 作業ディレクトリに依存せず、演習用の .env だけを読み込む。
# すでに設定された環境変数を優先する。
load_dotenv(Path(__file__).with_name(".env"), override=False)

# [注2] getenv で環境変数を読み、strip で前後の空白を除去する。
# 値が空なら or の右側を使うため、モデル名を設定しなくても既定値で動く。
# モデル名の指定と、そのモデルを API キーで利用できる権限は別のもの。
TEXT_MODEL = os.getenv("OPENAI_MODEL", "").strip() or "gpt-6-luna"
EMBEDDING_MODEL = (
    os.getenv("OPENAI_EMBEDDING_MODEL", "").strip() or "text-embedding-3-small"
)


def new_client():
    # [注3] API キーは呼び出し元を認証するための秘密の値。
    # ソースコードへ直接書かず、環境変数や Git 管理対象外の .env から渡す。
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    # [注4] 未設定やテンプレートのままの場合は、通信する前に案内を出して終了する。
    # この確認だけでキーの有効性やモデルの利用権限を判定できるわけではない。
    if not api_key or api_key == "your-api-key-here":
        raise SystemExit(
            "OPENAI_API_KEY を環境変数または scripts/api_basics/.env に設定してください。"
            "設定例は同じディレクトリの .env.example にあります。"
        )
    # [注5] OpenAI は公式 SDK のクライアント。生成しただけではモデルを呼び出さない。
    # timeout は通信待ちの秒数。SDK の自動再試行があるため、処理全体の時間とは異なる。
    return OpenAI(api_key=api_key, timeout=60.0)
