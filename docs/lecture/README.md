# 講義用ディレクトリ

講義教材と、学生が作成する学習メモ・演習記録を分けて管理します。

## ディレクトリ構成

```text
docs/lecture/
├── README.md
├── materials/
│   ├── git-github-ai-workshop.md
│   └── orm-database-debug-workshop.md
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

## 関連資料

[起動・検証ガイド](../setup.md) や [バックエンド API 仕様](../backend/api/) は、講義に限定しない技術資料として従来の場所で管理します。

以前の `docs/practice/` にあった学生の記述は `docs/lecture/students/` へ移動しました。以降の演習では新しいディレクトリを使用します。
