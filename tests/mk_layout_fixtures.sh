#!/usr/bin/env bash
# tests/fixtures/layout/ の見本を作り直す（中身は空に近いダミー。形だけを見る）。V3-M2 の形（PLAN.md 4.2）。
# 合格の見本は、出力フォルダそのもの（YYMMDD_<名前>/）を、検査にかける。
set -euo pipefail
cd "$(dirname "$0")/fixtures"
rm -rf layout && mkdir layout && cd layout
FILES="README.md 01_source.md 02_explanation_memo.md 11_question_and_answer.md 12_LLM_prompts_as_guide.md"
# set_out <フォルダ> <名前（日付を除く）>：1 件の形の出力フォルダを作る
set_out() {
  mkdir -p "$1/docs" "$1/.work/md"
  for f in $FILES; do echo "# $f" > "$1/$f"; done
  echo "# slides" > "$1/docs/$2-slides.md"; echo "<html></html>" > "$1/docs/$2-slides.html"
  echo "# src" > "$1/.work/md/$2.md"
}

# 合格：1 件
mkdir ok-single; set_out ok-single/261118_claude-code-plugin-guide claude-code-plugin-guide
# 合格：2 件以上（親の YYMMDD_ の下に 00_index.md と、子のフォルダ）
mkdir ok-multi; mkdir -p ok-multi/261120_report-pack/.work
set_out ok-multi/261120_report-pack/stock-review stock-review
set_out ok-multi/261120_report-pack/calc-stock calc-stock
printf '# 一覧\n- [stock-review](stock-review/README.md)\n- [calc-stock](calc-stock/README.md)\n' > ok-multi/261120_report-pack/00_index.md

# 不合格 1：v0.0.2 の形（explained/ と、直下のスライド）
mkdir bad-v002-shape; mkdir -p bad-v002-shape/261118_report/explained/out bad-v002-shape/261118_report/.work
for f in $FILES; do echo "# $f" > bad-v002-shape/261118_report/explained/$f; done
echo "# slides" > bad-v002-shape/261118_report/report-slides.md; echo "<html></html>" > bad-v002-shape/261118_report/report-slides.html
# 不合格 2：日付の無い名前（形は新しいが、名前が違う）
mkdir bad-no-date; set_out bad-no-date/report-guide report-guide
# 不合格 3：40 文字を超える名前
mkdir bad-long-name; set_out bad-long-name/261118_this-name-is-far-too-long-for-the-folder-rule-here claude-code-plugin-guide
# 不合格 4：スライドが docs/ の外
mkdir bad-slides-outside-docs; set_out bad-slides-outside-docs/261118_plugin-guide plugin-guide
mv bad-slides-outside-docs/261118_plugin-guide/docs/plugin-guide-slides.md bad-slides-outside-docs/261118_plugin-guide/
# 不合格 5：直下の中間ファイル
mkdir bad-intermediate-at-top; set_out bad-intermediate-at-top/261118_plugin-guide plugin-guide
echo "# src" > bad-intermediate-at-top/261118_plugin-guide/source.md
