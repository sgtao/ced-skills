# ced-skills

## Craft Explanation Docs Skills
URL・PDF・Word／Excel／PowerPoint・YouTube の動画から、**解説メモ**と**解説スライド**を、Claude Code への 1 回の指示で作るプラグインです。

> **ced** は **C**raft **E**xplanation **D**ocs（解説の資料を作る）の頭文字です。

- Craft：手をかけて作る
- Explanation：解説（読んだ人が内容を理解できるようにする説明）
- Docs：資料（Documents）

このプラグインに入っているスキルは、どれも「解説の資料を作る」仕事の一部を受け持ちます。そのため、スキルの名前には `ced-` を付けています。同じ働きの元のスキル（`url-to-md` など）を別に入れていても、名前で見分けられるようにするためでもあります。

| スキル | 受け持つこと |
|---|---|
| `ced-url-to-md` | URL・ファイル・YouTube を Markdown（見出しや表を書ける軽い文書の形式）にする |
| `ced-pdf-to-md-ja` | PDF を、表と図を保ったまま Markdown にする |
| `ced-craft-explanation-docs` | Markdown から、解説メモ一式（5 つのファイル）を作る |
| `ced-websearch-slide-ja` | 解説をスライド（Markdown と HTML）にする |

この 4 つを順に呼ぶ手順を 1 つのコマンド `/ced-skills:explain` にまとめてあります。**ふだん使うのはこのコマンドだけ**です。

## 何ができるか

```
入力（URL・PDF・動画など）
      ↓  /ced-skills:explain
出力（出力先のフォルダ。例：./explain-out/<入力の名前>/）
  ├── explained/           解説メモ 5 つ
  │     README.md／01_source.md／02_explanation_memo.md／11_question_and_answer.md／12_LLM_prompts_as_guide.md
  ├── <名前>-slides.md     解説スライド（編集用）
  ├── <名前>-slides.html   解説スライド（ブラウザで開く）
  └── .work/               変換した Markdown などの中間ファイル（使わなくてよい）
```

出力の形は、いつも同じです（解説メモは必ず `explained/` に入ります）。`<名前>` は、入力のファイル名（拡張子なし）や YouTube の動画 ID です。終わりの報告に、作ったファイルのパスが出ます。入力を 2 件以上まとめて渡したときの形は、`00_index.md`（一覧）と、入力ごとのフォルダになります。

| 出力 | 中身 |
|---|---|
| `01_source.md` | 入力を Markdown にしたもの（元の本文は変えない） |
| `02_explanation_memo.md` | 解説メモ（内容の整理と解説） |
| `11_question_and_answer.md` | 内容を確かめる FAQ（よくある質問と答え） |
| `12_LLM_prompts_as_guide.md` | 続きを AI に聞くためのプロンプト（質問の雛形）集 |
| `README.md` | 上の 4 つの案内 |
| スライド（`.md`・`.html`） | ブラウザで開けるスライド。`.md` は編集用 |

## 入力の種類

| 入力 | 例 | 作り方 |
|---|---|---|
| URL | `https://example.com/article` | Web ページを Markdown にする |
| PDF | `report.pdf` | 表と図を保って Markdown にする |
| Word・Excel・PowerPoint | `.docx`・`.xlsx`・`.pptx` | Markdown にする（旧形式の `.doc`・`.xls`・`.ppt` は LibreOffice が必要） |
| HTML | `page.html` | 本文を取り出して Markdown にする |
| YouTube | `https://www.youtube.com/watch?v=…` | 字幕（自動生成を含む）から作る |
| テキスト | `.txt`・`.csv`・字幕 `.vtt`・`.srt` など | Markdown に包む（字幕は時刻つきの本文にする） |
| コード | `.py`・`.js`・`.json` など | 言語名つきのコードブロックに包む |
| フォルダ | `./01_source/` | 中のファイルを 1 件ずつ処理する（秘密情報・隠しファイル・管理用のフォルダは読まない） |
| ZIP | `materials.zip` | 安全を確かめてから展開し、中のファイルを 1 件ずつ処理する |

入力が 2 件以上のときは、出力先に一覧（`00_index.md`）と、入力ごとのフォルダができます。上限（既定 5 件）を超えるときは、全件か先頭の上限までかを聞かれます（`--max-files` で変えられます）。質問を出さない実行（3 つの指定をすべて渡す）で上限を超えるときは、何も作らずに止まります。

## 必要なもの

| もの | 用途 | 必須か |
|---|---|---|
| [Claude Code](https://claude.com/claude-code) | このプラグインの実行 | 必須 |
| [uv](https://docs.astral.sh/uv/) | スキルの Python スクリプトの実行 | 必須 |
| Node.js（`npx` が使える版） | スライドの文法の検査（lint）と HTML の作成に使う `mdss-convert` を、`npx` が自動で取ってくる | スライドを作るときに必要 |
| Playwright | 作ったスライドを撮影して、見た目を確かめる | 任意（無ければ撮影を飛ばす） |

`uv` と Node.js は、それぞれの公式の手順で入れてください。`mdss-convert` は、自分で入れなくても `npx` が取ってきます。使えないときは、簡易な作り方に切り替わります。

## インストール

Claude Code を開き、次の 2 行を順に入力します（`/plugin` で始まる行は、Claude Code の入力欄に打つコマンドです）。

- カタログの登録
```
/plugin marketplace add sgtao/ced-skills
```

- プラグインのインストール
```
/plugin install ced-skills@ced-skills
```

- 1 行目：このリポジトリ（GitHub の `sgtao/ced-skills`）を、プラグインの配布元（marketplace）として登録する
- 2 行目：その中の `ced-skills` プラグインを入れる

入ったかどうかは、`/ced-skills:explain` と入力して候補に出れば確認できます。候補に出ないときは、`/plugin` で `ced-skills` が入っているか（有効か）を見て、それでも出なければ Claude Code を開き直してください。

手元にクローンしたフォルダから入れるときは、1 行目の `sgtao/ced-skills` を、そのフォルダのパスに替えてください。

### ツールごとの入れ方（Claude Code 以外）

入れ方は、ツールごとに違います。**4 つのスキル（`ced-url-to-md` など）は、どのツールにも同じものが入ります。** 違うのは、入れるコマンドと、「1 度の指示で解説メモとスライドを作る」入口が入るかどうかです。

- Claude Code：コマンド `/ced-skills:explain`（プラグインに入っています）
- そのほかのツール：スキル `ced-explain`（`install.sh` か、下の Gemini CLI の `--path adapters` で入ります）

「確認の状態」の読み方：**公式の文書で確認** は、コマンドの書き方を、そのツールの公式の文書で読んだ状態です（確認日 2026-11-19）。ced-skills そのものを、そのツールの実機で動かして確かめた、という意味ではありません。実機で動かしたものは、まだありません（対応ツールの表の「実機で確認済み」を見てください）。

| ツール | 入れ方（おすすめ） | 入るもの | 確認の状態 |
|---|---|---|---|
| Claude Code | プラグイン（上の 2 行） | 4 スキル＋コマンド | 検査済み（`plugin validate`・一時の設定での認識） |
| Copilot CLI | マーケットプレイス（下） | 4 スキル。コマンドは入らない見込み | コマンドは公式の文書で確認。ced-skills では未検証 |
| Gemini CLI | `gemini skills install`（下） | 4 スキル（`--path plugins`）、`ced-explain`（`--path adapters`） | コマンドは公式の文書で確認。ced-skills では未検証 |
| Codex | `install.sh --target agents` | 4 スキル＋`ced-explain` | 配置を検査済み。実機は未検証 |
| Antigravity | `install.sh --target antigravity` | 4 スキル＋`ced-explain` | 配置と再読み込みの方法は公式の文書で確認。実機は未検証 |

**Copilot CLI**（マーケットプレイスから入れる）

```
copilot plugin marketplace add sgtao/ced-skills
copilot plugin install ced-skills@ced-skills
```

Copilot CLI は、マーケットプレイスの設定を `.claude-plugin/marketplace.json` からも読みます（公式の文書）。ただしプラグインの `commands` は、Copilot では既定で読まれないので、`/ced-skills:explain` は使えない見込みです。`ced-explain` も入れたいときは、次のコマンドを使います（入れた後は、新しいセッションを開きます）。

```bash
bash scripts/install.sh --target copilot --scope user
```

**Gemini CLI**（Git のリポジトリから入れる）

```
gemini skills install https://github.com/sgtao/ced-skills.git --path plugins
gemini skills install https://github.com/sgtao/ced-skills.git --path adapters
```

1 つ目で 4 スキル、2 つ目で `ced-explain` が入ります。`--scope workspace` を付けると、今のプロジェクトだけに入ります。入れた後は、新しいセッションを開くか、`/skills reload` を入力します。クローンしたフォルダから入れるときは `bash scripts/install.sh --target agents --scope user` でも同じ場所（`~/.agents/skills`）に入ります。

**Codex**

```bash
bash scripts/install.sh --target agents --scope user
```

`~/.agents/skills` に入ります。Codex には `codex plugin marketplace add` というコマンドがありますが、ced-skills の `.claude-plugin/` の形式を、Codex の CLI が読むかどうかは、公式の文書から読み取れませんでした（未確認）。そのため、`install.sh` をおすすめします。表示されないときは、Codex を再起動します。呼び方は `$ced-explain` です。

**Antigravity**

```bash
bash scripts/install.sh --target antigravity --scope user
```

`~/.gemini/config/skills` に入ります（プロジェクトだけなら `--scope project` で `.agents/skills`）。入れた後は、`/skills reload` を入力します。`agy plugin install https://github.com/sgtao/ced-skills` は、リポジトリの直下に `plugin.json` がある場合の方法で、このリポジトリのプラグインは `plugins/` の下にあるため、この方法では入りません。

### プラグインを使わずに入れる（上級者向け）

プラグインが使えない環境では、スキルのフォルダへ直接コピーできます。

```bash
git clone https://github.com/sgtao/ced-skills.git
cd ced-skills
bash scripts/install.sh --scope user    # 既定は --target claude（~/.claude/skills へ入れる）
```

ツールごとの配置先は、`--target` で選びます（`bash scripts/install.sh --list-targets` で一覧）。

| `--target` | `--scope user` | `--scope project`（`--project-dir` の下） |
|---|---|---|
| `claude`（既定） | `~/.claude/skills` | `.claude/skills` |
| `agents`（別名 `codex`・`gemini`） | `~/.agents/skills` | `.agents/skills` |
| `copilot` | `~/.copilot/skills` | `.github/skills` |
| `antigravity` | `~/.gemini/config/skills` | `.agents/skills` |
| `all` | Claude・agents・antigravity の 3 か所（同じ場所は 1 回だけ） | `.claude/skills`・`.agents/skills` |

その他の指定：

```bash
bash scripts/install.sh --target all --scope project --project-dir <dir>   # 複数のツールへ、プロジェクトの下に入れる
bash scripts/install.sh --dir <フォルダ>                                  # 任意の配置先へ（単一の --target と使う。all とは使えない）
bash scripts/install.sh --scope user --dry-run                            # 何も書かず、行う操作だけ表示
bash scripts/install.sh --scope user -y                                   # 確認の問いを省く
bash scripts/install.sh --target copilot --scope user --uninstall         # ced- の 4 つだけ外す
```

プロジェクトの `.claude/skills` と `.agents/skills` の両方に入れると、Copilot CLI が両方を読むので、警告が出ます（どちらか一方にしてください）。

この方法では、**`/ced-skills:explain` は使えません**（コマンドは入らず、スキル 4 つだけが入ります）。代わりに [docs/instructions.md](docs/instructions.md) の「3. 自然文で頼む」の例文を Claude に渡してください。

## 使い方

### 1. まず 1 回、動かしてみる

```
/ced-skills:explain https://example.com/article
```

`https://example.com/article` の部分は、解説したい URL か、手元のファイルのパス（例：`./report.pdf`。Claude Code を開いたフォルダが基準）に替えます。YouTube の URL も使えます。

1 件で数分かかり、Claude の利用枠（API なら費用）を使います。記録した例では、HTML の記事 1 件で約 4.5 分、約 50 ターンでした。

すると、足りない情報だけが、**最初にまとめて**聞かれます。

| 聞かれること | 既定の答え |
|---|---|
| 出力先のフォルダ | `./explain-out/<入力の名前>` |
| スライドの枚数 | 6 枚 |
| 読み手 | 初めて読む人 |
| 入力の確認（未完了が 2 件以上、または参照元が 2 つあるとき） | 全件（上限の 5 件を超えるときは先頭 5 件だけ） |

答えると、変換 → 解説メモ → スライドの順に進み、最後に作ったファイルのパスが報告されます。

出力先に、前回の解説メモのフォルダが残っているときは、「続きから／別の名前で／やめる」のどれにするかを追加で聞かれます（上書きはされません）。

### 2. 質問を出さずに一気に動かす

答えを最初から渡すと、質問は出ません。

```
/ced-skills:explain ./report.pdf --out ./explain-out --slides 8 --audience 実務で使う人
```

| 指定 | 意味 |
|---|---|
| `--out <フォルダ>` | 出力先 |
| `--slides <枚数>` | スライドの枚数 |
| `--audience <読み手>` | 読み手の想定（例：`初めて読む人`／`実務で使う人`／`専門家`） |

貼り付け用の例は [docs/instructions.md](docs/instructions.md) にあります。

### 3. 使うときの注意

- YouTube 動画は、字幕（日本語・英語。自動生成を含む）から解説を作ります。字幕が無い動画では、字幕が取れなかった理由が報告されます。その場合は、別の動画に差し替えて、もう一度実行してください。
- 作業用の中間ファイルは `.work/` と `explained/out/` にまとまっています。解説メモの 5 つとスライドだけを使えば足ります。
- 入力を Markdown にできなかったときは、理由を報告して止まります。
- スライドの `.md` や `.html` は、同じ名前のものがあると上書きされることがあります。残したいものは、先に別のフォルダへ移してください。

---

# 開発者向け

ここから先は、このリポジトリを直したり、テストしたりする人向けの説明です。使うだけなら読まなくて構いません。

## ファイル構成

```
ced-skills/
├── .claude-plugin/marketplace.json     リポジトリ自体を marketplace にする（プラグインの置き場は ./plugins）
├── plugins/                            プラグイン ced-skills の根（.claude-plugin/plugin.json がここにある）
│   ├── .claude-plugin/plugin.json
│   ├── ced-url-to-md/  ced-pdf-to-md-ja/  ced-craft-explanation-docs/  ced-websearch-slide-ja/
│   └── commands/explain.md             総合インストラクション
├── adapters/ced-explain/SKILL.md       Claude Code 以外のツール向けの ced-explain（生成物。手で直さない）
├── CHANGELOG.md                        変更履歴（版ごとの追加・変更・修正と、未検証のこと）
├── docs/instructions.md                総合インストラクションの例（貼り付け用）
├── scripts/install.sh                  スキルを、ツールごとの skills フォルダへ直接入れる・外す
├── scripts/sync_skills.py              元のリポジトリから複製し、名前を置き換える
├── scripts/build_explain_skill.py      explain.md から adapters/ced-explain を生成する
└── tests/                              合格条件の検査
```

## 既存の同名スキルを外す（重なりを避けるとき）

元の名前のスキル（`url-to-md`・`pdf-to-md-ja`・`craft-explanation-docs`・`websearch-slide-ja`）が `~/.claude/skills` に入っていると、同じ言葉に両方が反応します。`ced-` の接頭辞で名前は区別されますが、起動の言葉は同じです。

- 元のリポジトリの `install.sh --uninstall` を使う、または
- 手で `~/.claude/skills/<名前>` のフォルダを消す

このリポジトリの `install.sh --uninstall` が消すのは `ced-` の 4 つだけで、元の名前のスキルには触りません。

## 複製と更新

スキルは元のリポジトリ（開発用の `01_sources`）から複製しています（`scripts/sync_skills.py`）。この GitHub のリポジトリだけを取得した場合、`01_sources` は無いので、この操作はできません。

```bash
python3 scripts/sync_skills.py            # 元から複製し直す（ced- を付ける）
python3 scripts/sync_skills.py --check    # 複製が、元に名前の置き換えを当てた結果と一致するか確かめる
python3 scripts/sync_skills.py --list     # 置き換えた箇所を一覧する
```

直したいときは、元のリポジトリで直してから、この `sync_skills.py` で取り込みます。複製の中を直接書き換えないでください。

## テスト

| 確かめること | コマンド |
|---|---|
| プラグインの検査（validate、警告 0） | `bash tests/check_plugin.sh` |
| 一時の設定で入れて、5 つ（スキル 4・コマンド 1）が認識される | `bash tests/test_plugin_install.sh` |
| 複製が元と一致する | `python3 scripts/sync_skills.py --check` |
| install.sh（4 ツールと all、2 つのスコープ、--uninstall、--dry-run、ced-explain の配置） | `python3 tests/test_install.py` |
| 元のテスト（11・12）を複製に向けて実行 | `bash tests/run_source_tests.sh`（外すものは `tests/source-exclusions.txt`） |
| YouTube の字幕の選択（地域付きの言語コード en-US を含む） | `python3 tests/test_caption_track.py` |
| explain の質問・出力の形・入力の決め方（静的検査。`--stream` で E2E の記録も見る） | `python3 tests/check_explain.py` と `python3 tests/test_check_explain.py` |
| ced-explain が生成結果と一致し、禁止した語句が無い | `python3 tests/check_portable.py` と `python3 scripts/build_explain_skill.py --check` |
| README に、古い字幕の注意が無く、入力の種類・対応表・構成が載っている | `python3 tests/check_readme.py` |
| 出力の形（見本 2 つが合格、不合格の見本 3 つが不合格） | `python3 tests/test_check_output_layout.py` |
| 実際の出力の形 | `python3 tests/check_output_layout.py <出力フォルダ>` |
| E2E（HTML・PDF・YouTube の出力）の検査（形も含む） | `python3 tests/e2e_check.py <出力フォルダ>` |

入力の前処理（`collect_sources.py`）の検査は、元のリポジトリ 11 の `tests/test_collect_sources.py` にあり、`run_source_tests.sh` が複製に向けて実行します。

`sync_skills.py` と `run_source_tests.sh` は、元のリポジトリ（開発用の `01_sources`）が隣にあるときだけ動きます。E2E は `claude -p` を使う有料の処理です。記録は `tests/e2e-record/` にあります。

## 対応ツール

| ツール | 呼び方 | ユーザー単位の配置先（`--target`） | 配置を検査済み | 実機で確認済み |
|---|---|---|---|---|
| Claude Code | `/ced-skills:explain` | `~/.claude/skills`（プラグインで入れる） | ✓（プラグインの検査と `install.sh` のテスト） | 未検証（v0.0.2 の H1〜H5 で確かめる） |
| Codex | `$ced-explain` | `~/.agents/skills`（`--target agents`） | ✓（`install.sh` のテスト） | 未検証（H6） |
| Copilot CLI | `/ced-explain`（`/skills reload` のあと） | `~/.copilot/skills`（`--target copilot`） | ✓（`install.sh` のテスト） | 未検証（H6） |
| Gemini CLI | 説明文の依頼で選ばれる（新しいセッションか `/skills reload` のあと） | `~/.agents/skills`（`--target agents`） | ✓（`install.sh` のテスト） | 未検証（H6） |
| Antigravity | `/ced-explain`（`/skills reload` のあと） | `~/.gemini/config/skills`（`--target antigravity`） | ✓（`install.sh` のテスト） | 未検証（H6） |

- Claude Code では、ced-explain は入りません（コマンド `/ced-skills:explain` を使います）。ほかのツールには、スキルの `ced-explain` が入ります（生成元は `plugins/commands/explain.md`。`adapters/ced-explain/SKILL.md` は生成物で、手で直しません）。
- Codex は、既定でネットワークが無効です。URL や YouTube を取る場合は、設定が要る見込みです。

## 対応と制限

- 対応ツールは下の表のとおりです。Claude.ai 用の ZIP は対象外です。
- 「配置を検査済み」は、一時の場所に入れて、配置先と中身をテストで確かめた状態です。「実機で確認済み」は、そのツールの画面で実際に認識されたことを確かめた状態です。確かめていないものは「未検証」と書いています。
- スクリプトは `uv run` で動きます（標準の `python3` が 3.10 より古いときも動くように）。
- スライドの撮影（Playwright）と lint（`mdss-convert`）は、Node.js が入っていることを前提にします（`mdss-convert` は `npx` で取得）。
- `tests/e2e-record/` の記録は、構成を変える前（`plugins/ced-skills` を指す時点）のものです。

## ライセンス

このリポジトリは MIT（`LICENSE`）です。複製したスキルの元のライセンスは、元のリポジトリごとに違い、`ced-url-to-md` の元のリポジトリには LICENSE ファイルがありません。再配布するときは、複製したスキルの扱いを確かめてください。
