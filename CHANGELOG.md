# CHANGELOG

ced-skills（Claude Code のプラグインと、スキル 4 つ）の変更履歴です。版は `plugins/.claude-plugin/plugin.json` の `version` と、Git のタグに合わせます。

---
## [0.0.3] - 2026-11-21

### 追加
- **E2E の集計**：`tests/e2e_check.py` が 2 件以上の出力を、子のフォルダごとに 7・8 で確かめる（`<子の名前>/<基準>`）。子が 2 件未満なら `7_units` で不合格
- **出力フォルダの名前**：`ced_name.py`（`ced-url-to-md`）が、`YYMMDD_<英小文字・数字・->`（`_` の後ろは 40 文字以内）の候補を 3 つ作る。同じ入力の既存フォルダは `--resume` で先頭の候補にする（再実行で `-2` にならない）
- **題と日付**：`collect_sources.py plan` が、出力フォルダ名の材料（`title`・`date`・`date_source`・`head`）と、再開できる既存のフォルダ（`resumable`）を返す。日付は、YouTube・Web の公開日、PDF・Office の作成日、Markdown の `published` など。取れなければ実行した日
- **`collect_sources.py fetch`**：Web ページ・YouTube を、今いるフォルダの `01_sources/YYMMDD_<名前>.md` に取得する。同じ URL は通信せずに同じファイルを返す
- **解説済みを飛ばす**：引数なしの実行で、他の出力フォルダで `done` の項目を飛ばす（`ALREADY_EXPLAINED`。全部なら `ALL_EXPLAINED`）
- **2 件以上のときの子フォルダの名前**：ファイル名から、拡張子なし・英小文字・数字・`-`・40 文字以内（例：`stock-review`）で自動で決める。重なると `-2`。旧は `e2e-input__stock-review.pdf` のように記号と拡張子を含み、出力の形の検査に落ちていた。形の検査は、macOS の `.DS_Store` を無視する
- **子フォルダの名前の安定**：解説済みのあとにファイルを足しても、既存の子の名前はずれない（前回の記録を引き継ぐ）。旧い形の名前の記録は、`OLD_SLUG_FORMAT` で止めて案内する（2 件以上のときだけ）
- **実行前の環境確認**：`/ced-skills:explain` が、最初に `python3 --version` で版を確かめ、3.10 未満や依存が無いときは `uv run --python 3.12` で動かす

### 変更
- **来歴**：0.0.2 までは元のリポジトリ（11・12・13）から `sync_skills.py` で複製していた。0.0.3 からは `plugins/ced-*` を直接直す。同期の仕組み（`sync_skills.py`・`sources.lock.json`・`run_source_tests.sh`）は消し、テストは `tests/source/` に移した
- **`check_docs.py` の `--out-dir`**：out/ の場所を指定できる（既定は作業フォルダの `out/`）。`explain` は移した `.work/out/` を渡す
- **出力の形**（互換なし）：今いるフォルダの直下の `YYMMDD_<名前>/`（解説メモは直下、スライドは `docs/`）。`explain-out/` と `explained/` はやめた
- **`ced-craft-explanation-docs` を単独で使ったときの既定の作業フォルダ**：入力の隣の `<名前>_explained/` から、今いるフォルダの直下の `YYMMDD_<名前>/`（スライドは直下の `docs/`）に変えた。理由：`/ced-skills:explain` の形と揃えるため（`--dest` を渡せば、これまでどおり好きな場所に作れる）

---
## [0.0.2] - 2026-11-19

### 追加
- **入力の拡大**：URL・ファイル・YouTube に加えて、**テキスト・コード・字幕（`.vtt`・`.srt`）・フォルダ・ZIP** を入力にできる。複数のファイルは、ファイルごとに解説メモとスライドを 1 組ずつ作り、一覧（`00_index.md`）を作る。上限は既定 5 件（`--max-files`、`--source-dir`）。秘密情報・隠しファイル・管理用のフォルダ・シンボリックリンクは読まない。ZIP は、安全を確かめてから展開する（展開先の外を指す名前、リンク、暗号化、容量・件数・圧縮率の超過、壊れた ZIP は止める）。入力の前処理は、`ced-url-to-md` の `collect_sources.py`（`plan`・`prepare`・`mark`・`index`）
- **`ced-explain`**：Claude Code 以外のツール向けの入口（スキル）。`plugins/commands/explain.md` から `scripts/build_explain_skill.py` で生成する（`adapters/ced-explain/`）
- **他ツールへの配置**：`install.sh` に `--target`（`claude`・`agents`〔別名 `codex`・`gemini`〕・`copilot`・`antigravity`・`all`）。README に、ツールごとの入れ方と対応表（配置を検査済みか、実機で確認済みか）
- 検査：出力の形（`check_output_layout.py`）、`ced-explain`（`check_portable.py`）、README（`check_readme.py`）、explain の静的検査の拡張、会話の記録の集計（`check_explain.py --transcript`）、`install.sh` のテスト（4 ツール・2 スコープ）
- 手動確認の手順書（H1〜H6）は、開発の記録（`05_logs`）にある。H2 用の入力 `tests/fixtures/e2e/e2e-input.zip`

### 変更
- **質問は最初の 1 回だけ**：`/ced-skills:explain` は、足りない答え（出力先・枚数・読み手、必要なら入力の確認）を、最初に 1 回（最大 4 問）にまとめて聞く。そのあと、解説メモとスライドの途中で質問しない。3 つの指定（`--out`・`--slides`・`--audience`）をすべて渡すと、質問は 0 回。出力先が衝突したときは、再度聞かずに `OUTPUT_CONFLICT` で止まる
- **出力の形を固定**：`<出力先>/explained/`（解説メモ 5 つ）、`<名前>-slides.md`・`<名前>-slides.html`、`.work/`（中間ファイル）。別名のフォルダや入れ子を作らない。既定の出力先は `./explain-out/<入力の名前>`（0.0.1 は `./explain-out`）
- **`--audience` を内容の向きとして扱う**：読み手を話題として扱わない（0.0.1 は、読み手の名前が解説の話題になることがあった）
- **`[toTopPage]` が飛べるようになった**：リンク先を `./README.md` にした（0.0.1 の `../README.md` は、作業フォルダの外を指していた）。見出し「Proposed Prompts」を「LLM 用プロンプト」にそろえ、「解説メモ一式」と「解説メモ」の用語を分けた（元のリポジトリ 12）
- `install.sh`：`--scope` などの値を省いたときに、足りないオプションを伝える。`--help` の先頭の行を直した。プロジェクトで `.claude/skills` と `.agents/skills` の両方に入れるときは、警告する
- README：古い YouTube の字幕の注意を直した。入力の種類、ツールごとの入れ方、ファイル構成とテストの表を足した

### 修正
- Python 3.10・3.11 で、`collect_sources.py` が構文エラーになる不具合（f 文字列の書き方）を直した。3.10 以上で動く

---
## [0.0.1] - 2026-11-18

初回のリリース。

### 追加
- スキル 4 つ（`ced-url-to-md`・`ced-pdf-to-md-ja`・`ced-craft-explanation-docs`・`ced-websearch-slide-ja`）。元のリポジトリから複製し、名前に `ced-` を付けた（`scripts/sync_skills.py`）
- コマンド `/ced-skills:explain`：URL・PDF・Word／Excel／PowerPoint・YouTube から、解説メモ 5 つと、解説スライド（MD・HTML）を 1 度の指示で作る
- Claude Code のプラグイン（`.claude-plugin/marketplace.json`、`plugins/.claude-plugin/plugin.json`）
- `scripts/install.sh`：プラグインを使わずに、`--scope user`・`project`・`--dir` で入れる・外す（`--uninstall`・`--dry-run`）
- LICENSE（MIT）、README（ced の由来、インストール、使い方）

### 修正
- 英語の YouTube の字幕を選べるようにした（地域付きの言語コード `en-US` などを、字幕のキーに合わせる）
- 生成 AI の総括の視点を子箇条書きにし、検査 C-12 を足した

---
