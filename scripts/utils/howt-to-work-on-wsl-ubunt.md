開発者向けメモ — Windows / WSL / Ubuntu での動作を安定させる

目的
- ホストが Windows（CRLF, NTFS）でも WSL / Ubuntu（LF, ext4）でも同じように開発できるようにするための手順と注意点。

基本方針
- スクリプトは LF にする（.gitattributes を追加済み）。既にチェックアウト済みのファイルは変換が必要。
- 開発時にホストのファイルをコンテナにバインドマウントする場合、ホスト側の改行や実行ビットがそのままコンテナに反映されるため注意。

推奨ワークフロー
1) WSL を使う（Windows + Docker Desktop の場合）
   - WSL の Linux ファイルシステム（例: /home/<user>/workspace）にリポジトリを置くとファイルの動作が安定します。

2) 既に Windows 上でチェックアウトしている場合（CRLF の可能性あり）
   - WSL で以下を実行して改行と実行ビットを修正してください：

```bash
# WSL で実行
sudo apt update
sudo apt install -y dos2unix
# プロジェクトルートで
dos2unix backend/entrypoint.sh
dos2unix ollama/entrypoint.sh
chmod +x backend/entrypoint.sh ollama/entrypoint.sh
# 一括で直す場合（付属スクリプト）
./scripts/fix-line-endings.sh
```

3) Git設定
   - 推奨: 開発マシンで `git config core.autocrlf false` にして、プロジェクトの `.gitattributes` に従う運用がシンプルです。
   - 既存のチェックアウトを LF に揃えるには、一度ファイルを変換後、再コミットしてください。

Dockerfile の堅牢化
- イメージ内にコピーした entrypoint を `/usr/local/bin` に置き、イメージ内で CR を取り除く処理を追加しています。これにより、バインドマウントでホストのファイルが原因で直ちに落ちる問題を緩和します。

トラブルシュート
- `env: 'sh\r': No such file or directory` が出たら改行（CRLF）が残っています。`sed -n '1p' backend/entrypoint.sh | sed -n l` で `^M` を確認できます。
- `frontend` の nginx が `host not found in upstream "backend"` を出す場合は、まず `backend` が起動しているかログで確認してください。

その他
- CI 上でも改行や linter のチェックを入れると再発しにくくなります。

---
必要なら、このファイルをさらに詳細化して、Windows 固有の Git 設定や VSCode の自動改行設定なども追記します。要望があれば教えてください。