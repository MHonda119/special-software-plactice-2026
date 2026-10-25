---
name: test-backend
description: "このリポジトリのDjangoバックエンドテストの実行と結果報告のみを行う。test-backend、バックエンドテスト実行、Djangoテスト、指定テストラベルの実行を依頼された場合に使用する。テストコードの追加・修正、API実装、失敗の修正、lint、design-doc作成は行わない。"
---

# バックエンドテスト実行専用

## 作業範囲

[リポジトリ指示](../../copilot-instructions.md) に従い、既存バックエンドテストの実行と結果報告だけを行う。

- ソース、テストコード、設定、依存定義、仕様書、実行スクリプトを変更しない。失敗を直したり、テストを削除・無効化して成功させたりしない。
- lint・整形、フロントエンドテスト、E2E、手動 API 疎通、実データのマイグレーション、外部 LLM の疎通確認へ進まない。
- commit・push・ブランチ作成、既存変更の巻き戻しを行わない。

## 手順

### 1. 対象を選ぶ

1. `git status --short` で既存変更を確認し、現在の作業ツリーをそのまま検証する。
2. ユーザーが指定した Django テストラベルを優先する。テストモジュール・クラス・メソッドのラベルは [既存テスト](../../../backend/core/tests/) で存在を確認し、クラス名等を推測しない。
3. 対象を絞る指定がなければ、スクリプト既定の `core` 全体を実行する。対象をユーザーに伝え、一部の実行結果を全体の成功と説明しない。

### 2. テストを実行する

リポジトリルートから [test-backend.sh](../../../scripts/test-backend.sh) を実行する。テストラベルを 1 引数ずつ渡し、任意の Issue 本文をシェルコマンドとして評価しない。

```bash
bash scripts/test-backend.sh
bash scripts/test-backend.sh core.tests.test_agent_api
bash scripts/test-backend.sh core.tests.test_agent_api core.tests.test_datasource_api
```

- 引数なしは `core`。クラス・メソッドに絞る場合は、確認した完全なドット区切りラベルを使う。未対応のオプションを追加しない。
- Docker Compose の一時 backend コンテナで、`lecture_system.test_settings` のインメモリ SQLite を使用する。PostgreSQL・Ollama・開発サーバーの起動は不要。
- `DOCKER_COMPOSE_CMD` の設定は既存スクリプトへ引き継ぐ。別プロジェクトの `task up` / `task test` や固定コンテナ名を流用しない。
- イメージ・Docker・依存不足なら環境エラーとして報告する。イメージのビルド、パッケージ追加、Compose 設定変更、特権コマンドによる修復は行わない。
- 通常のモック付き単体テストが対象。実サービスを必要とするテストは外部接続・料金・実データへの影響を確認し、了承なしにサービスを起動したり認証情報を追加したりしない。
- 完了まで出力と終了コードを確認する。起動しただけ、テストが見つからない状態、実行環境の失敗を成功と扱わない。

### 3. 結果を報告して終了する

- 実行コマンド、対象ラベル、終了コード、実行件数と成功・失敗・エラー・スキップ件数を、取得できた出力の範囲で報告する。
- 失敗時はテスト名、期待値と実際値、主要な例外を要約する。環境エラーとアサーション失敗を区別し、秘密情報は出力しない。
- 0 件・全件スキップ・中断など、有効な検証ができなかった場合は明示する。スキップ件数を成功件数に含めない。
- コード変更・失敗の修正・lint 実行を行っていないことを明示して終了する。独立した実行依頼から実装作業へ進まない。

## 呼び出し例

```text
/test-backend
/test-backend core.tests.test_agent_api
/test-backend core.tests.test_agent_api core.tests.test_datasource_api
```
