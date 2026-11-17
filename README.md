# ced-skills

任意のドキュメント・情報（URL・PDF・ファイル・YouTube）から、**解説メモ**と**解説スライド**（MD・HTML）を 1 度の指示で作る Claude Code のプラグインです。

同梱するもの:
- スキル 4 つ（名前に `ced-` を付けた複製。中身は元のスキルと同じ）
  - `ced-url-to-md`：URL・ファイル・YouTube を Markdown にする
  - `ced-pdf-to-md-ja`：PDF を、表と図を保った Markdown にする
  - `ced-craft-explanation-docs`：Markdown から、解説メモ一式（5 本）を作る
  - `ced-websearch-slide-ja`：解説をスライド（MD・HTML）にする
- コマンド 1 つ：`/ced-skills:explain`（4 スキルを連携させる手順）

## 入れ方

### A. プラグインとして入れる（推奨）

```
/plugin marketplace add <このリポジトリのパス または GitHub の owner/repo>
/plugin install ced-skills@ced-skills
```

### B. スキルのフォルダへ直接入れる（プラグインを使わない）

```bash
bash scripts/install.sh --scope user                          # ~/.claude/skills へ
bash scripts/install.sh --scope project --project-dir <dir>   # <dir>/.claude/skills へ
bash scripts/install.sh --dir <フォルダ>                      # 任意の配置先へ
bash scripts/install.sh --scope user --dry-run                # 何も書かず、行う操作だけ表示
bash scripts/install.sh --scope user -y                       # 確認の問いを省く
```

対象は Claude Code だけです。`--list-targets` で配置先を確かめられます。

**B で入れた場合、`/ced-skills:explain` は使えません**（コマンドは入らず、スキル 4 つだけが入ります）。代わりに [docs/instructions.md](docs/instructions.md) の「3. 自然文で頼む」の例文を Claude に渡してください。外すときは `bash scripts/install.sh --scope user --uninstall`（`ced-` の 4 つだけが消えます）。

## 使い方

```
/ced-skills:explain <URL または ファイルのパス> [--out <フォルダ>] [--slides <枚数>] [--audience <読み手>]
```

足りない答えだけ、1 回にまとめて聞かれます。例と詳しい使い方は [docs/instructions.md](docs/instructions.md) にあります。

## 既存の同名スキルを外す（重なりを避けるとき）

元の名前のスキル（`url-to-md`・`pdf-to-md-ja`・`craft-explanation-docs`・`websearch-slide-ja`）が `~/.claude/skills` に入っていると、同じ言葉に両方が反応します。`ced-` の接頭辞で名前は区別されますが、起動の言葉は同じです。

- 元のリポジトリの `install.sh --uninstall` を使う、または
- 手で `~/.claude/skills/<名前>` のフォルダを消す

このリポジトリの `install.sh --uninstall` が消すのは `ced-` の 4 つだけで、元の名前のスキルには触りません。

## 複製と更新

スキルは `01_sources` の元のリポジトリから複製しています（`scripts/sync_skills.py`）。

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
| install.sh（3 つのスコープ、--uninstall、--dry-run） | `python3 tests/test_install.py` |
| 元のテスト（11・12）を複製に向けて実行 | `bash tests/run_source_tests.sh`（外すものは `tests/source-exclusions.txt`） |
| explain の質問の扱い | `python3 tests/check_explain.py --stream tests/e2e-record/m1-html/stream.jsonl` |
| E2E（HTML・PDF・YouTube の出力）の検査 | `python3 tests/e2e_check.py <出力フォルダ>` |

E2E は `claude -p` を使う有料の処理です。記録は `tests/e2e-record/` にあります。

## 対応と制限

- 対応は Claude Code だけです（Claude.ai 用の ZIP や Copilot などは、元のリポジトリの `install.sh` を使ってください）。
- スクリプトは `uv run` で動きます（標準の `python3` が 3.10 より古いときも動くように）。
- スライドの撮影（Playwright）と lint（`mdss-convert`）は、Node.js と `mdss-convert` が入っていることを前提にします。入れ方はこの README では扱いません（`mdss-convert` と `uv` は、それぞれの公式の手順で入れてください）。
- YouTube の字幕は、英語の自動字幕だと取れないことがあります（既知の不具合。下の「既知の問題」）。

## 既知の問題
- 英語の YouTube 動画で、字幕が取れずに概要欄だけで解説が作られることがあります。出力の中身を必ず確かめてください。
- 出力フォルダの中に、中間ファイル（`out/` や `.work/`）が混ざることがあります。解説メモは `out/` の直下か `explained/` にできます。

## ライセンス

このプラグインの `plugin.json` は MIT と書いています。複製したスキルの元のライセンスは、元のリポジトリごとに違います（`ced-url-to-md` の元には LICENSE がありません）。公開前に確かめてください。
