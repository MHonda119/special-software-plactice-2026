---
name: check-lint
description: "このリポジトリのlintチェックと結果報告のみを行う。check-lint、lint確認、Ruff、ESLint、静的検査の実行を依頼された場合に使用する。backend・frontend・両方を対象に選び、コード修正、自動修正、整形、テスト実行、API実装、design-docの作成は行わない。"
---

# Lint チェック専用

## 作業範囲

lint の実行と結果報告だけを行う。[リポジトリ指示](../../copilot-instructions.md) と既存の lint 設定を使い、ソース・設定・仕様書は変更しない。

- `--fix`、`--unsafe-fixes`、formatter、Prettier、`ruff format` などの自動修正・整形を実行しない。
- 単体テスト、E2E、API 疎通、マイグレーション、API 実装、design-doc 作成へ進まない。
- lint 違反を発見しても修正せず、場所・ルール・内容を報告して終了する。
- commit・push・ブランチ作成、lint 設定の追加・緩和、既存変更の巻き戻しを行わない。

## 手順

### 1. 対象を決める

1. ユーザー指定の `backend` / `frontend` / `all` を優先する。
2. 指定がなければ会話の対象に合わせ、Backend API の文脈では backend、フロントエンドの文脈では frontend を選ぶ。対象を判断できない場合は両方を選び、実行前に範囲を伝える。
3. `git status --short` で既存変更を確認する。未コミット変更は保持し、現在の作業ツリーを検査する。
4. 既存スクリプトは各領域全体を検査する。ファイル限定の実行と誤って説明しない。

### 2. lint を実行する

リポジトリルートで、対象に対応する既存スクリプトだけを実行する。引数を追加しない。

| 対象     | コマンド                        | 検査内容                         |
| -------- | ------------------------------- | -------------------------------- |
| backend  | `bash scripts/lint-backend.sh`  | Django コードに対する Ruff       |
| frontend | `bash scripts/lint-frontend.sh` | TypeScript の静的型検査と ESLint |
| all      | 上記 2 コマンドを個別に実行     | 両方の結果を報告                 |

実装は [lint-backend.sh](../../../scripts/lint-backend.sh) と [lint-frontend.sh](../../../scripts/lint-frontend.sh) を参照する。独自のラッパーや新しい lint ルールを追加しない。

- `all` では一方が lint 違反で終了しても、もう一方を実行してそれぞれの結果を残す。
- Docker Compose の一時コンテナを使用する。PostgreSQL・Ollama・開発サーバーの起動は不要。
- `DOCKER_COMPOSE_CMD` が設定されていれば、既存スクリプトにそのまま処理させる。
- 既存スクリプト内の依存準備以外に、パッケージ追加・イメージのビルド・Compose 設定変更・特権コマンドで環境を修復しない。
- Docker・イメージ・ネットワーク・依存不足で実行できなければ、その対象は未実施または環境エラーとする。lint 成功と扱わない。
- backend/frontend 用コマンドは、すべての `.github/` 補助スクリプトや Markdown まで検査するものではない。対象外のファイルが依頼に含まれる場合は、対応する既存設定・コマンドを確認し、不明なら確認を求める。

### 3. 結果を報告して終了する

対象ごとに以下をまとめる。

- 実行コマンドと終了コード。
- 成功、lint 違反、環境エラー、未実施の区別。
- 違反のファイル・行・ルール名と短い説明。重複はまとめ、秘密情報は出力しない。
- 検査対象外・途中で停止したチェックがあれば、その範囲と理由。
- コード変更・自動修正・テスト実行を行っていないこと。

エディタの診断だけを、コマンドによる全体 lint の成功として報告しない。コマンドが終了するまで結果を確認し、違反の修正には着手しない。

## 呼び出し例

```text
/check-lint backend
/check-lint frontend
/check-lint all
```
