# CHANGELOG

ced-skills（Claude Code のプラグインと、スキル 4 つ）の変更履歴です。版は `plugins/.claude-plugin/plugin.json` の `version` と、Git のタグに合わせます。

スキルの中身（`plugins/ced-*`）は、元のリポジトリ（url-to-md、pdf-to-md-ja、craft-explanation-docs、websearch-slide-ja）から複製したものです。元の変更は、それぞれのリポジトリの CHANGELOG を見てください。複製がどの版かは `sources.lock.json` にあります。

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

### 確かめたこと
- 合格条件 1〜5・8〜10 の機械検査（プラグインの検査、複製と元の一致、元のテスト、一時の設定での認識、`install.sh`、入力の前処理、出力の形、`ced-explain`、README）
- 質問の数は、手順書の静的検査まで（条件 6）

### 未検証（0.0.2 では確かめていない）
- 対話での質問の数（手順書の H2〜H5）。最後の E2E（ZIP 2 件を入力にした実行。条件 7）
- 実機の各ツール（Codex・Copilot CLI・Gemini CLI・Antigravity）で、スキルが認識されること。README の「実機で確認済み」は、すべて「未検証」
- 再インストールの後に、再起動が要るか（H1）
- 入力が HTML・YouTube のときの実出力は、0.0.1 の記録のまま
- 独立した審査（reviewer）と仕込み検査

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
