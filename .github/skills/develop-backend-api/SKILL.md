---
name: develop-backend-api
description: "Django REST FrameworkのBackend API作成・変更・不具合修正Issueを進める。仕様検討、実装、テスト、lintを必要な段階の専用Skillへ分けて扱う進行役。仕様書作成のみはcreate-api-doc、テスト実行のみはtest-backend、lintのみはcheck-lintを使い、依頼範囲を広げない。"
---

# Backend API 開発の進行役

## 必要な Skill だけを読む

[リポジトリ指示](../../copilot-instructions.md) を優先し、以下の Skill は該当段階に入る時だけ本文を読む。全 Skill・テンプレート・参照資料を最初にまとめて読み込まず、手順やコマンドをここに重複記載しない。リンクを置くだけでは Skill は自動実行されない。

| 段階・依頼                 | 参照する Skill                                     | 渡す内容                                          |
| -------------------------- | -------------------------------------------------- | ------------------------------------------------- |
| API 仕様の検討・仕様書更新 | [create-api-doc](../create-api-doc/SKILL.md) | Issue、対象 API、現行仕様か変更案か               |
| バックエンドテスト実行     | [test-backend](../test-backend/SKILL.md)           | 対象テストラベル。共有変更では `core` 全体        |
| lint 確認                  | [check-lint](../check-lint/SKILL.md)               | 対象 `backend`。frontend 変更時だけ必要範囲を追加 |

- 仕様書だけ・テスト実行だけ・lint だけの依頼は、該当 Skill に従って結果を報告し、実装や他の段階へ進まない。
- 開発全体の依頼では、各専用 Skill の作業範囲をその段階で守り、結果を受け取った本 Skill が次段階や修正の要否を判断する。専用 Skill 自身に実装・失敗修正・別段階への継続をさせない。
- 段階間には対象、決定事項、ファイル、コマンド・結果、未確定事項だけを引き継ぐ。参照本文を毎回再掲しない。

## 開発の手順

1. Issue の要件と依頼範囲を確認する。本文を取得できなければ提示を求め、内容を推測しない。既存変更を保持し、破壊的変更・権限・外部接続の未確定事項を確認する。
2. [API 索引](../../../docs/backend/api/README.md) と対象の仕様書、[ルート](../../../backend/core/urls.py) から処理を決めるコード・隣接テストだけを読む。現状、期待仕様、未確定事項を分ける。
3. 契約の検討・文書更新が必要なら `create-api-doc` を参照する。仕様相談だけならここで終了する。開発全体なら契約確定後に実装へ進む。
4. 変更を否定できる最小のテストを選び、再現テストを追加する。可能なら `test-backend` の手順で変更前の失敗を確認する。
5. 最小の実装変更を行い、直後に `test-backend` の手順で対象テストを実行する。失敗時は本 Skill の実装段階へ戻って修正し、同じ検証を繰り返してから隣接変更へ進む。
6. 共有挙動を変えた場合はテスト範囲を広げ、`check-lint` で確認する。実装した契約の仕様書更新は `create-api-doc` に従い、Draft と現行仕様の区別を保つ。
7. 変更、各検証結果、未実施とその理由、残る互換性・運用上の注意点を報告する。ユーザーが求めない commit・push・ブランチ作成は行わない。

## 実装段階に残す要点

- 入力検証は Serializer、HTTP 境界は View、処理は既存 Usecase 等に置き、ルート登録を忘れない。既存の `build_llm_client`、`RagChatRunner`、`datasource_store` を再利用する。
- テスト追加・失敗修正は本 Skill の実装作業であり、実行専用の `test-backend` には含めない。既存の `TestCase` / `APIClient` と参照先への patch に合わせ、LLM・Chroma 等の外部 I/O をモック化する。
- Model 変更時だけマイグレーションを作成し、未作成差分と既存データへの影響を確認する。副作用・外部依存・Model 変更の詳しい観点が必要な時だけ [API 契約・テスト観点](./references/api-contract.md) の関連節を読む。
- API 契約を変える場合は [既存設計資料](../../../backend/documents/) と [API クライアント](../../../frontend/src/services/apiClient.js) への影響を確認する。無関係な修正、料金・秘密情報・実データを伴う無断の外部呼び出しは行わない。

## 補助ツールが必要な時

- ルート一覧や実装済み仕様の静的照合だけが必要なら [api_inventory.py](./scripts/api_inventory.py) の `--help` を確認する。静的照合は挙動のテストではなく、未実装の Draft に実装との完全一致を要求しない。
- [run_checks.sh](./scripts/run_checks.sh) は既存の補助ツールとして残すが、各専用 Skill の代わりに `all` を無条件に実行しない。
- 補助スクリプト自体を変更した時だけ [専用の回帰テスト](./scripts/tests/test_tools.py) を確認する。通常の API 開発ではソースやテスト全文を読み込まない。
