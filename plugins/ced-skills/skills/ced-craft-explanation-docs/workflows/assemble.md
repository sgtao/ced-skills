# 転記（assemble）

`out/` の中間生成物を、作業フォルダの最終ファイルに組み立てる。**LLM は手で写さない**（`assemble.py` が行う。手で写すと、形のずれ・字数の誤りが出る）。
`<RUN>` と `<SKILL_DIR>` は SKILL.md の定義。オプションは `--help` が正。

```bash
<RUN> <SKILL_DIR>/scripts/assemble.py --help
```

## 前提

- 作業フォルダに `README.md`・`01_source.md`・`out/00_manifest.json` がある（取り込み済み）。
- `out/` に `02_overview.md`・`03_deep-questions.md`・`04_grouping.md`・`05_group-analysis-<N>.md`（グループの数だけ）・`06_summary.md`・`07_reflection.md`・`08_faq.md`・`10_system-prompt.md`・`11_sample-questions.md` がある。書式は `references/output-formats.md` の「3-1. out/ の各ファイルの書式」のとおり。

## 手順

1. 実行する。
   ```bash
   <RUN> <SKILL_DIR>/scripts/assemble.py <作業フォルダ>
   ```
   標準出力の JSON（`written`・`unchanged`・`groups`・`foreign_sections`・`warnings`）を読む。書く前に確かめたいときは `--dry-run`。
2. `MISSING_OUT_FILE` で止まったら、標準エラーの理由（足りないファイルや、足りない見出し・数）を読み、**足りない `out/` のファイルを作る・直す**（該当する Step を実行する）。そのあと、もう一度実行する。最終ファイルを直接直さない。
3. 終わったら、検査へ進む（`workflows/review.md`）。

## assemble.py がすること

| 最終ファイル | 内容 |
|---|---|
| `02_explanation_memo.md` | `out/02` の §1〜5（見出しを 1 段下げる。§6 は写さない）、`out/03` の回答を各問の下に、`out/05-N` を「## テーマ：」に、`out/07` を「## 活用案」に（各案の末尾に実測の字数） |
| `11_question_and_answer.md` | `out/08` をグループごとに（番号を全体の通し番号にそろえる） |
| `12_LLM_prompts_as_guide.md` | `out/10` をコードブロックに、`out/11` を「## 活用例：サンプル質問」に。モデル名は `out/10` のメタ情報の `> モデル:` |
| `README.md` | 「## 生成AIの総括」の本文を `out/06` で置き換える |
| `out/00_manifest.json` | `foreign_sections`（スキルが作っていない節のハッシュ）を更新する |

- **2 回実行しても結果は同じ**。内容が同じファイルは書き直さない（更新時刻も変わらない）。
- **利用者が足した `##` の節**（スキルが作っていない節）は、元の位置に残す。
- `01_source.md` と入力の Markdown は変えない。

## してはいけないこと

- `scripts/assemble.py` を書き換えない。失敗は `REASON=` の行をそのまま報告する。
- 最終ファイルを手で直さない。直すのは `out/` の元のファイル（直したら `assemble.py` をやり直す）。
- 活用案の末尾の `（N字）` を手で書かない（スクリプトが実測で書く）。
