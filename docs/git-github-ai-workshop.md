# Git・GitHub・Copilot・MCP・Skills 基礎演習

この演習では、Gitの基本操作から始めて、Issueに書いた小さな課題を実装し、Pull Request（PR）で提出します。後半では、Visual Studio Code（以下、VS Code）のGitHub CopilotとGitHub MCP、Agent Skillsを使い、同じ開発の流れを体験します。

題材は**自分の学習メモをMarkdownでRepositoryに追加すること**です。内容はぶっちゃけ何でもいいです。本リポジトリのアプリやDockerを起動する必要はありません。

## 到達目標と進め方

演習を終えたら、次のことができるようになることを目指します。

- ファイルの変更を確認し、必要な変更だけをコミットする。
- Issue → ブランチ → 変更 → コミット → push → PR → レビューの流れを説明する。
- `gh`でGitHubのIssueやPRを操作する。
- CopilotがGitHub MCPを使ったことを確認し、取得したIssueをもとに変更する。
- 短いSkillを作り、Copilotで利用する。

| 項目 | 内容 |
| --- | --- |
| 準備 | ツール・認証・参加権限・clone |
| 演習1 | Gitの基本コマンドをローカルで練習 |
| 演習2 | GitHubの画面でIssueを作り、PRで提出 |
| 演習3 | `gh`でIssue・PRを確認し、PRを更新 |
| 演習4 | VS Code Copilot × GitHub MCP |
| 演習5 | VS Code Copilot × Skills |


## 0. 準備

### 0-1. 用意するもの

- GitHubアカウント
- 講義リポジトリへの書き込み権限（コラボレーターの招待を承諾済み）
- Git 2.28以降、GitHub CLI（`gh`）
- 最新の安定版VS Codeと、GitHub Copilotのチャットが使える環境
- インターネット接続

WindowsではGit BashまたはWSLのターミナル、macOS・Linuxでは通常のターミナルを使います。以下のコマンド例はBash・zsh向けです。VS Codeの「ターミナル」→「新しいターミナル」から実行できます。

インストールがまだの場合は、[Git](https://git-scm.com/downloads)、[GitHub CLI](https://cli.github.com/)、[VS Code](https://code.visualstudio.com/)の公式案内を参照してください。Copilotの利用可否や利用上限はアカウント・学校の設定によって異なります。演習1〜3はCopilotなしで実施できます。

```bash
git --version
gh --version
```

Gitに記録する名前とメールアドレスを設定します。値は自分のものに置き換えてください。公開したくないメールアドレスがある場合は、GitHubの「Settings」→「Emails」で確認できるnoreplyアドレスを使えます。

```bash
git config --global user.name "Your Name"
git config --global user.email "GitHubで使用するメールアドレス"
```

すでに設定している場合は、次のコマンドで確認するだけで構いません。

```bash
git config --global --get user.name
git config --global --get user.email
```

GitHub CLIの初回認証を行います。`GitHub.com` → `HTTPS` → ブラウザでログインする方法を選び、Gitの認証にも使うか聞かれたら「Yes」を選びます。

```bash
gh auth login
gh auth status
```

### 0-2. この教材で使う名前

| 表記 | 置き換える内容 |
| --- | --- |
| `YOUR_ID` | 自分のGitHubユーザー名。ファイル・ブランチ・Skill名では小文字を使う |
| Issue番号 `123` | 演習2で作成したIssueの実際の番号 |
| PR番号 `456` | 演習2で作成したPRの実際の番号 |

例えばユーザー名が`student-a`なら、`docs/practice/YOUR_ID.md`は`docs/practice/student-a.md`になります。`123`や`456`は例示用の番号なので、そのまま実行しないでください。

### 0-3. 講義リポジトリをcloneする

本教材では、全員が**講義リポジトリ内に自分の作業ブランチを作り、同じリポジトリの`main`へPRを出す方式**で進めます。

1. [講義リポジトリ](https://github.com/MHonda119/special-software-plactice-2026)をブラウザで開きます。
2. 講師からのコラボレーター招待を承諾し、書き込み権限があることを確認します。招待が届いていない場合は、講師に自分のGitHubユーザー名を伝えてください。
3. 作業用の親フォルダで、次を実行します。

```bash
git clone https://github.com/MHonda119/special-software-plactice-2026.git
cd special-software-plactice-2026
git remote -v
```

`origin`が`https://github.com/MHonda119/special-software-plactice-2026.git`を指していることを確認します。すでにこの講義リポジトリをcloneしている場合は、そのフォルダを使い、cloneを省略してください。

学生は自分の作業ブランチにpushし、`main`への反映はPRのレビュー後に講師・管理者が行います。他の学生のブランチやファイルは、演習の編集対象に含めません。

VS Codeの「ファイル」→「フォルダーを開く」で、このフォルダを開きます。`code`コマンドが使える場合は、`code .`でも開けます。

### 0-4. 最初に覚える言葉

| 言葉 | 意味 |
| --- | --- |
| Git | 手元のファイルの変更履歴を管理するツール |
| GitHub | Gitのリポジトリを共有し、IssueやPRで共同作業するサービス |
| リポジトリ | ファイルと変更履歴をまとめたもの |
| clone | リポジトリを手元のPCに取得する操作 |
| ブランチ | 作業を分けるための履歴の枝。`main`は基本となるブランチ |
| ステージ | 次のコミットに含める変更を選ぶ場所 |
| コミット | 選んだ変更を、説明とともに履歴として記録する操作 |
| push / pull | 手元の履歴をGitHubに送る操作 / リモートの更新を手元に取り込む操作 |
| Issue | やること・困っていること・完了条件を書く場所 |
| PR | ブランチの変更を取り込んでもらうための提案 |
| レビュー / マージ | 変更を確認すること / 変更を取り込むこと |

## 1. 演習1：Gitの基本コマンド

**目標：変更 → add → commitの流れを、GitHubを使わずに体験する。**

### 1-1. 小さな練習用リポジトリを作る

VS Codeのターミナルで、講義リポジトリの**外側**に移動して練習フォルダを作ります。`git init`は、この練習フォルダだけで実行します。

```bash
cd ..
mkdir git-basics-sandbox
cd git-basics-sandbox
git init -b main
git status
```

VS Codeで`git-basics-sandbox`を開き、`note.md`を作成して保存します。

```markdown
# Gitの練習

Gitはファイルの変更履歴を管理するツールです。
```

```bash
git status
```

`note.md`が「Untracked files」（Gitがまだ追跡していないファイル）に表示されます。

### 1-2. addしてからcommitする

```bash
git add note.md
git status
git diff --staged
git commit -m "docs: Gitの練習メモを追加"
git log --oneline -5
```

`git add`でステージに載せ、`git commit`で履歴に記録します。**コミットしただけではGitHubには送られません。**

### 1-3. 変更内容を確認する

`note.md`の末尾に、次の1行を追加して保存します。

```markdown
コミットする前に差分を確認します。
```

```bash
git status
git diff
git add note.md
git diff --staged
git commit -m "docs: 差分確認の説明を追加"
git log --oneline -5
```

`git diff`はまだステージに載せていない変更、`git diff --staged`は次のコミットに入る変更を表示します。`git add`の後にさらに編集した場合は、その変更も含めるためにもう一度`git add`します。

> `git log`や`git diff`が画面いっぱいに表示されて操作できなくなったら、`q`で表示を終了できます。

### 1-4. addを取り消してみる

`note.md`に好きな1行を追加して保存し、次を実行します。

```bash
git add note.md
git restore --staged note.md
git status
```

ファイルの編集内容は残り、ステージからだけ外れます。再び`git add`してコミットしてください。

> **確認**
>
> - `git log --oneline -5`で、自分のコミットを確認できた。
> - `git status`と`git diff`の役割を説明できる。
> - `git restore --staged`で、編集内容を残してaddを取り消せた。

## 2. 演習2：IssueからPRまで

**目標：GitHubの画面とGitを使い、学習メモをPRとして提出する。**

開発の流れは次のとおりです。

```text
Issueでやることを決める → ブランチを作る → 編集・確認する
→ add・commit → push → PRを作る → レビュー → マージ
```

### 2-1. 講義リポジトリにIssueを作る

[講義リポジトリのIssues](https://github.com/MHonda119/special-software-plactice-2026/issues)で「New issue」を選びます。テンプレート選択が表示された場合は「Documentation」を使います。

タイトル例：`[演習] YOUR_IDのGit・GitHub学習メモを追加する`

本文例：

```markdown
## 目的
Git・GitHub・AI開発支援の使い方を、自分の言葉で説明できるようにする。

## 作業内容
- docs/practice/YOUR_ID.mdを追加する。
- Git、GitHub、gh、MCP、Skillsで学んだことを記録する。

## 完了条件
- [ ] GitとGitHubの違いを説明している。
- [ ] 基本コマンドを3つ以上、用途とともに書いている。
- [ ] gh、MCP、Skillsを使って気づいたことを書いている。
- [ ] Markdownのプレビューで読みやすさを確認している。
- [ ] Issueを参照したPRを提出している。
```

Issueを作成し、URLと番号を控えます。以降の例では、その番号を`123`としています。

### 2-2. 講義リポジトリへ戻り、ブランチを作る

VS Codeで`special-software-plactice-2026`を開き直し、新しいターミナルを開きます。以降の操作は、すべてこのリポジトリのルートで実行します。

```bash
git status
git switch main
git pull --ff-only origin main
git switch -c test/YOUR_ID-git-github
git branch --show-current
```

`git status`で作業中の変更がないことを確認してから切り替えます。最後のコマンドで、`test/YOUR_ID-git-github`と表示されれば準備完了です。

`git pull --ff-only origin main`は講義リポジトリの更新を取得します。`--ff-only`は、履歴が分岐している場合に自動でマージせず停止する指定です。この演習では`main`を直接編集せず、作業ブランチで変更します。

### 2-3. 自分の学習メモを追加する

```bash
mkdir -p docs/practice
```

VS Codeで`docs/practice/YOUR_ID.md`を作成します。次の例をもとに、GitとGitHubの項目を**自分の言葉**で書きます。残りの項目は後半の演習で追記します。

```markdown
# Git・GitHub学習メモ

## Git
- Gitで管理できること：
- git statusの用途：
- git addの用途：
- git commitの用途：

## GitHub
- Gitとの違い：
- Issueの役割：
- PRの役割：

## gh
後の演習で追記する。

## MCP
後の演習で追記する。

## Skills
後の演習で追記する。
```

エディタ右上のプレビュー操作、またはコマンドパレットの`Markdown: Open Preview`で見た目を確認します。

### 2-4. 確認・コミット・push

```bash
git status
git add docs/practice/YOUR_ID.md
git diff --staged
git commit -m "docs: YOUR_IDのGit・GitHub学習メモを追加"
git push -u origin test/YOUR_ID-git-github
```

新規ファイルは、addする前の`git diff`には通常表示されません。`git diff --staged`で内容を確認してください。`-u`を付けた初回pushの後は、同じブランチなら`git push`だけで送れます。

### 2-5. GitHubの画面でDraft PRを作る

push後に表示されたURL、または講義リポジトリの「Pull requests」→「New pull request」から作成します。

| 項目 | 選択するもの |
| --- | --- |
| repository | `MHonda119/special-software-plactice-2026` |
| base（取り込み先） | `main` |
| compare（作業ブランチ） | `test/YOUR_ID-git-github` |

タイトル例：`[演習] YOUR_IDのGit・GitHub学習メモを追加`

本文例：

```markdown
Closes #123

## 変更内容
- 自分用の学習メモを追加しました。
- 現在はGit・GitHubの項目を記載し、後半の演習で追記します。

## 確認したこと
- Markdownのプレビューで表示を確認しました。
- コミットするファイルが自分の学習メモだけであることを確認しました。
```

「Create pull request」のメニューから**Draft PR**を選びます。Draftは作業途中であることを示す状態です。PRのURLと番号を控えます。以降の例では`456`としています。

`Closes #123`は、同じリポジトリのIssueとの関連を示します。このPRが講義リポジトリの既定ブランチ`main`へマージされると、対応するIssueが自動で閉じられます。

**演習3〜5では同じPRを更新します。追記のたびに新しいPRを作る必要はありません。**

### 2-6. レビューの進め方

1. ペアの学生または講師にPRのURLを共有します。
2. レビュー担当は「Files changed」で差分を読み、「コマンドの説明が分かるか」「読みやすいか」を確認します。
3. 改善点があれば、具体的なコメントを1つ書きます。
4. 作成者は修正し、同じブランチへコミット・pushします。

レビュー内容を受けて修正するときも、演習2-4と同じ手順です。PRには新しいコミットが自動で追加されます。講義リポジトリへのマージは、講師・管理者が判断します。

> **確認**
>
> - Issueに目的と完了条件を書いた。
> - 講義リポジトリ内の自分の作業ブランチにpushできた。
> - 講義リポジトリの`main`を宛先とするDraft PRを作れた。
> - PRの「Files changed」に、自分の学習メモが表示されている。

## 3. 演習3：ghコマンドを使う

**目標：GitHubの画面で行った確認・更新を、ターミナルから行う。**

`git`は手元の履歴を操作し、`gh`はGitHubのIssueやPRなどを操作します。本教材では、操作対象を明確にするため、`--repo`で講義リポジトリを明示します。

### 3-1. IssueとPRを確認する

```bash
gh issue list --repo MHonda119/special-software-plactice-2026
gh issue view 123 --repo MHonda119/special-software-plactice-2026
gh pr list --repo MHonda119/special-software-plactice-2026
gh pr view 456 --repo MHonda119/special-software-plactice-2026
gh pr diff 456 --repo MHonda119/special-software-plactice-2026
```

次のコマンドはPRをブラウザで開きます。

```bash
gh pr view 456 --repo MHonda119/special-software-plactice-2026 --web
```

### 3-2. Issueに進捗コメントを書く

```bash
gh issue comment 123 --repo MHonda119/special-software-plactice-2026 --body "学習メモを追加し、Draft PR #456を作成しました。"
```

ブラウザでIssueを開き、コメントが投稿されたことを確認します。コメントには自分が実際に終えた作業を書きます。

### 3-3. 学習メモを更新して、同じPRに反映する

`docs/practice/YOUR_ID.md`の「gh」を更新します。

- 実行した`gh`コマンドを1つ、用途とともに書く。
- `git`と`gh`の違いを1文で書く。

```bash
git diff
git add docs/practice/YOUR_ID.md
git diff --staged
git commit -m "docs: ghの学習内容を追記"
git push
gh pr diff 456 --repo MHonda119/special-software-plactice-2026
```

### 3-4. ghでIssue・PRを作る方法を読む

演習2で作成したIssue・PRはそのまま使います。以下は、**次回、新しい課題に取り組むときの作成例**です。今回のIssue・PRを重複して作成するためには実行しません。

Issue本文を`issue-body.md`という一時ファイルに書いた場合：

```bash
gh issue create --repo MHonda119/special-software-plactice-2026 --title "[演習] 学習メモを追加する" --body-file issue-body.md
```

PR本文を`pr-body.md`に書き、作業ブランチをpush済みの場合：

```bash
gh pr create --repo MHonda119/special-software-plactice-2026 --base main --head test/YOUR_ID-git-github --draft --title "[演習] 学習メモを追加" --body-file pr-body.md
```

`--head ブランチ名`で講義リポジトリ内の自分の作業ブランチを指定します。一時ファイルは提出対象ではありません。コミットするファイルは個別に指定してください。

> **確認**
>
> - `gh`で自分のIssue・PR・差分を確認できた。
> - Issueへ進捗コメントを投稿できた。
> - 同じPRに「gh」の追記が反映されている。

## 4. 演習4：VS Code Copilot × GitHub MCP

**目標：CopilotにGitHubのIssueを取得してもらい、内容をもとに手元のファイルを更新する。**

MCP（Model Context Protocol）は、AIが外部のツールやサービスを使うための共通の仕組みです。GitHub MCPを接続すると、CopilotがGitHub上のIssueやPRをツールで取得・操作できます。

この演習では、**GitHubの情報取得はMCP、手元の編集はCopilotのファイル編集機能、コミット・pushは自分のGit操作**で進めます。

### 4-1. CopilotとGitHub MCPを準備する

1. VS Codeで講義リポジトリのルートを開きます。
2. Copilotのチャットを開き、GitHubアカウントでサインインします。
3. チャットのモードから「Agent」を選びます。環境によって複数のエージェントが表示される場合は、手元のワークスペースを編集するローカルのものを使います。
4. コマンドパレットを開き、`MCP: Add Server`を実行します。
5. HTTP形式のサーバーを選び、URLに`https://api.githubcopilot.com/mcp/`を入力します。
6. 名前を`github`とし、自分のユーザー設定に保存します。保存先の表示はバージョンによって`User`や`Global`などと異なります。
7. `MCP: List Servers`から`github`を選んで起動し、認証が求められたらブラウザでGitHubへログインします。
8. チャットのツール一覧で、GitHub MCPのツールが利用できることを確認します。

これはGitHub公式のリモートMCPサーバーです。ローカルのMCPサーバーをDockerで起動する手順は不要です。`gh auth login`とMCPの認証は別なので、MCP側でもログインが求められることがあります。

表示される接続先や権限を読んでから認証してください。学校や組織のポリシーで利用できない場合は、講師に状況を共有します。

<details>
<summary>手動設定が必要な場合：VS Code形式の設定例</summary>

リポジトリのルートに`.vscode/mcp.json`を作る場合の設定例です。既存の設定があれば、`servers`へ`github`を追加します。

```json
{
  "servers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/"
    }
  }
}
```

このリポジトリでは`.vscode/`が`.gitignore`に含まれているため、上記ファイルは通常コミットされません。トークンを直接書く必要はありません。

新しいVS Codeでは、ポータブル形式の`.mcp.json`も案内されます。そちらはトップレベルのキーが`mcpServers`です。ファイル名と形式を混ぜず、画面の案内または[公式の設定資料](https://code.visualstudio.com/docs/copilot/reference/mcp-configuration)に従ってください。

</details>

### 4-2. MCPでIssueを取得する

Copilotに次のように依頼します。番号は自分のIssueに置き換えます。

```text
GitHub MCPを使い、MHonda119/special-software-plactice-2026の
Issue #123を取得してください。
目的、作業内容、完了条件を日本語で整理してください。
この段階ではファイル編集、投稿、Issueの変更をしないでください。
```

チャット内のツール呼び出し表示を開き、**GitHub MCPのツールでIssueを取得したか**を確認します。Issueを取得せずに回答した場合は、GitHub MCPのツールが有効か確認し、もう一度依頼します。

AIの文章だけで判断せず、ブラウザのIssue本文と比較してください。ツール名はサーバーのバージョンによって変わるため、名前の暗記は不要です。

### 4-3. 完了条件をもとに学習メモを編集する

続けて、次の依頼を送ります。

```text
取得したIssueの完了条件と、docs/practice/YOUR_ID.mdを確認してください。
「MCP」の節に、GitHub MCPでIssueを取得した流れと、
GitHubの画面の内容と照合して気づいたことを短く追記してください。
変更するのはこのファイルだけにしてください。
私が気づいたことは「ここに自分の気づきを書く」です。
commit、push、GitHubへの投稿は行わず、変更内容を説明してください。
```

「ここに自分の気づきを書く」を実際の気づきに置き換えます。Copilotが提案した変更は差分を読み、内容が合っている場合に採用します。

```bash
git status
git diff
git add docs/practice/YOUR_ID.md
git diff --staged
git commit -m "docs: GitHub MCPの学習内容を追記"
git push
```

### 4-4. MCPでPRに進捗コメントを投稿する

次の文章を読み、自分の作業と一致していることを確認してから依頼します。

```text
GitHub MCPを使い、MHonda119/special-software-plactice-2026の
PR #456に、次のコメントを1件投稿してください。
「GitHub MCPでIssueの完了条件を確認し、学習メモのMCP欄を更新しました。
差分を自分で確認してからコミット・pushしました。」
PRの本文や状態は変更しないでください。
```

ツール実行の確認画面が表示された場合は、投稿先と本文を確認して実行します。GitHubのPR画面でコメントを確認します。MCPの書き込み権限がない場合は、本文をPR画面から手動で投稿し、MCPでの投稿は未実施と記録してください。

> **確認**
>
> - GitHub MCPのツール呼び出しを確認できた。
> - AIの整理した内容を、実際のIssueと比較した。
> - Copilotが編集した差分を読み、自分でコミット・pushした。
> - MCPによるPRコメントを確認した、または未実施の理由を記録した。

## 5. 演習5：VS Code Copilot × Skills

**目標：繰り返し使う作業手順をSkillとして保存し、Copilotから利用する。**

Skillは、AIに作業の進め方を伝えるための指示と、必要に応じた関連ファイルをまとめたものです。この演習では、Markdownの指示ファイル`SKILL.md`を1つだけ作ります。
学習メモを所定の手順にしたがって作成するSkillを例示していますが、自由に作成してみて構いません。

| 仕組み | この演習での役割 |
| --- | --- |
| MCP | GitHubに接続し、IssueやPRを取得・操作する |
| Skills | 学習メモをどの手順・形式で整理するかを伝える |
| `.github/copilot-instructions.md` | リポジトリ全体で共通の開発方針を伝える |

本リポジトリには、共通のCopilot指示と`skill-creator`という既存Skillがあります。今回はそれらを編集せず、学生ごとの小さなSkillを追加します。

### 5-1. 自分のSkillを作る

演習2で作った作業ブランチのまま進めます。

```bash
git branch --show-current
mkdir -p .github/skills/study-note-YOUR_ID
```

`.github/skills/study-note-YOUR_ID/SKILL.md`を作り、次を貼り付けます。**フォルダ名と`name`の`YOUR_ID`を、自分のユーザー名の小文字表記に置き換えてください。**

````markdown
---
name: study-note-YOUR_ID
description: Git・GitHub演習の学習メモを整理する。学習メモの追記、振り返り、提出前の確認を依頼されたときに使う。
---

# 学習メモを整理する

1. 対象のMarkdownファイルを確認する。パスが不明なら利用者に聞く。
2. ファイルを読み、Git、GitHub、gh、MCP、Skillsの見出しを確認する。
3. 利用者が伝えた学習内容を、該当する見出しの下へ簡潔に追記する。
4. 既存の文章を尊重し、内容が重複する場合はまとめる。
5. 実行していない操作や確認を、実施済みとして書かない。不明な点は「未確認」と書く。
6. 指定された学習メモ以外のファイルを編集しない。
7. commit、push、GitHubへの投稿は行わない。
8. 最後に、変更内容と利用者が確認する点を日本語で伝える。
````

冒頭の`---`で囲んだ部分はYAML形式の設定です。`name`はSkillの名前、`description`は「何をするか・いつ使うか」を表します。`name`には小文字の英数字とハイフンを使い、フォルダ名と一致させます。ファイル名は大文字の`SKILL.md`です。

### 5-2. Skillを利用する

1. ファイルを保存し、VS Codeでリポジトリのルートを開いていることを確認します。
2. 新しいCopilotチャットを開きます。
3. チャット入力欄で`/`を入力し、`study-note-YOUR_ID`を選びます。
4. 続けて、次の依頼を入力します。

```text
/study-note-YOUR_ID docs/practice/YOUR_ID.mdを整理してください。
今回学んだことは「Skillsは繰り返す作業手順を保存して使えること」です。
Skillsの節に、この説明と今回の使い方を追記してください。
```

`description`に合う依頼からSkillが自動で利用される場合もありますが、この演習では`/`から明示的に選んで確認します。

Skillが表示されない場合は、フォルダと`name`の一致、`SKILL.md`のファイル名、保存状態、VS Codeの更新を確認します。必要ならコマンドパレットの`Developer: Reload Window`で再読み込みします。設定にAgent Skillsを有効にする項目があるバージョンでは、それも確認してください。

### 5-3. 指示と結果を比べる

```bash
git status
git diff
```

次を確認します。

- 「Skills」の節に、伝えた学習内容が追記されたか。
- 実施していない作業が、実施済みと書かれていないか。
- 指定した学習メモ以外を、Copilotが編集していないか。

チャット内にSkillを読み込む表示があれば、それも確認します。**出力の形式が合っているだけでは、Skillが使われた証拠にはなりません。**一覧に表示されず、ファイルをチャットへ添付して指示を読ませた場合は、「手動で指示を参照した」と記録します。

### 5-4. Skillと学習メモをPRへ反映する

新しいSkillは未追跡ファイルなので、addした後にその内容も確認します。

```bash
git add .github/skills/study-note-YOUR_ID/SKILL.md docs/practice/YOUR_ID.md
git diff --staged
git commit -m "docs: 学習メモ整理Skillと振り返りを追加"
git push
```

同じPRの「Files changed」に、学習メモと自分の`SKILL.md`が表示されることを確認します。

> **確認**
>
> - 自分の`SKILL.md`を作成した。
> - Skillを選んで使い、指示と結果を比較した。
> - 学習メモとSkillを同じPRに反映した。


### 6. マージされた後の更新

講義リポジトリへマージされた後、手元の`main`を更新します。作業中の変更がないことを確認してから実行します。

```bash
git status
git switch main
git pull --ff-only origin main
```

これで手元の`main`が更新されます。次の課題では、更新した`main`から新しいブランチを作ります。

## 7. コマンド早見表

| コマンド | 用途 |
| --- | --- |
| `git init -b main` | 新しいローカルリポジトリを作る |
| `git clone URL` | リモートのリポジトリを手元へ取得する |
| `git status` | 変更・ステージの状態を確認する |
| `git diff` | ステージに載せていない変更を見る |
| `git diff --staged` | 次のコミットに入る変更を見る |
| `git add ファイル` | コミットに含める変更を選ぶ |
| `git restore --staged ファイル` | 編集内容を残し、ステージから外す |
| `git commit -m "説明"` | ステージの変更を履歴に記録する |
| `git log --oneline -5` | 最近のコミットを確認する |
| `git switch -c ブランチ名` | 新しいブランチを作って切り替える |
| `git switch main` | `main`へ切り替える |
| `git remote -v` | リモートの接続先を確認する |
| `git pull --ff-only origin main` | 講義リポジトリの更新を取り込む |
| `git push -u origin ブランチ名` | ブランチを初めてpushする |
| `git push` | 設定済みの接続先へ追加コミットを送る |
| `gh auth status` | GitHub CLIのログイン状態を確認する |
| `gh issue list / view / create / comment` | Issueを一覧・表示・作成・コメントする |
| `gh pr list / view / diff / create / ready` | PRを一覧・表示・差分確認・作成・レビュー可能にする |

`gh`の行はサブコマンドの一覧です。`/`を含む行をそのまま実行するのではなく、演習中の実行例を参照してください。詳しい使い方は`gh issue --help`や`gh pr --help`でも確認できます。

## 8. 困ったとき

| 状況 | 最初に確認すること |
| --- | --- |
| `not a git repository`と表示された | ターミナルが目的のリポジトリ内にあるか確認する |
| `nothing to commit`と表示された | ファイルを保存したか、`git add`したかを`git status`で確認する |
| 新規ファイルが`git diff`に出ない | `git status`で確認し、add後に`git diff --staged`を見る |
| pushで認証エラーになった | `gh auth status`を確認する。HTTPS認証を設定するには`gh auth setup-git`を使う |
| pushで権限エラーになった | `origin`が講義リポジトリを指しているか、ログインしたアカウントで招待を承諾し書き込み権限を得ているか確認する |
| IssueやPRが見つからない | `--repo`の指定と、自分のIssue・PR番号を確認する |
| ブランチを切り替えられない | `git status`で未コミットの変更を確認し、必要な変更をコミットする |
| pullやpushが履歴の分岐で停止した | 状態を講師に共有する。演習ではforce pushで解消しない |
| MCPのツールが出ない | サーバーの起動・認証・Agentモード・ツールの有効化を確認する |
| Skillが出ない | リポジトリのルート、保存状態、ファイル名、`name`とフォルダ名の一致を確認する |
| AIが余計な編集をした | VS Codeの差分表示で内容を確認し、不要な提案を取り消す |


## References

VS Code・Copilotの画面や機能は更新されます。メニュー名が異なる場合は、使用中のバージョンの公式案内を参照してください。

- [Git：公式の入門書 Pro Git（日本語）](https://git-scm.com/book/ja/v2)
- [GitHub：GitHub Flow](https://docs.github.com/ja/get-started/using-github/github-flow)
- [GitHub：IssueとPRをリンクする](https://docs.github.com/ja/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)
- [GitHub CLI：マニュアル](https://cli.github.com/manual/)、[gh pr create](https://cli.github.com/manual/gh_pr_create)
- [VS Code：GitHub Copilotの設定](https://code.visualstudio.com/docs/copilot/setup)
- [VS Code：MCPサーバーの利用](https://code.visualstudio.com/docs/copilot/customization/mcp-servers)
- [GitHub：公式GitHub MCP Server](https://github.com/github/github-mcp-server)
- [VS Code：Agent Skills](https://code.visualstudio.com/docs/copilot/customization/agent-skills)
