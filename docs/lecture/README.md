# 講義用ディレクトリ

講義教材と、学生が作成する学習メモ・演習記録を分けて管理します。

## ディレクトリ構成

```text
docs/lecture/
├── README.md
├── materials/
│   ├── git-github-ai-workshop.md
│   ├── orm-database-debug-workshop.md
│   ├── react-agent-backend-lecture.md
│   ├── react-agent-backend-implementation.md
│   └── react-agent-local-development.md
└── students/
    ├── README.md
    └── nattoinf.md
```

| ディレクトリ | 用途 |
| --- | --- |
| [materials](materials/) | 講師が配布する講義教材・演習手順を格納します。 |
| [students](students/) | 学生が自分の学習メモ・演習記録を作成します。記述方法は [学生用の案内](students/README.md) を参照します。 |

## 教材一覧

- [Git・GitHub・Copilot・MCP・Skills 基礎演習](materials/git-github-ai-workshop.md) では、Git の基本操作と AI 開発支援を扱います。
- [バックエンド演習: ORM・データベース・テスト・デバッグ](materials/orm-database-debug-workshop.md) では、Auth API と Session API を題材に保存処理とデバッグを扱います。
- [バックエンド実装講義: Usecase を中心に ReAct Agent を組み込む](materials/react-agent-backend-lecture.md) では、2 コマ各 90 分の講義構成、到達目標、責務分担、評価基準を示します。
- [ReAct Agent バックエンド実装資料](materials/react-agent-backend-implementation.md) では、参照スクリプトをもとに Usecase、View、Serializer、Model を接続する実装手順とテスト例を扱います。
- [ReAct Agent ローカル開発・動作確認](materials/react-agent-local-development.md) では、Compose / Vite の起動、GPT-6 luna の登録、UI での二往復と状態表示、検証・エラー切り分けを扱います。

## 関連資料

[起動・検証ガイド](../setup.md) や [バックエンド API 仕様](../backend/api/) は、講義に限定しない技術資料として従来の場所で管理します。

以前の `docs/practice/` にあった学生の記述は `docs/lecture/students/` へ移動しました。以降の演習では新しいディレクトリを使用します。
