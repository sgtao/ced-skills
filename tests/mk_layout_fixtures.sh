#!/usr/bin/env bash
# tests/fixtures/layout/ の見本を作り直す（中身は空に近いダミー。形だけを見る）
set -euo pipefail
cd "$(dirname "$0")/fixtures"
rm -rf layout && mkdir layout && cd layout
FILES="README.md 01_source.md 02_explanation_memo.md 11_question_and_answer.md 12_LLM_prompts_as_guide.md"
memo() { mkdir -p "$1/out"; for f in $FILES; do echo "# $f" > "$1/$f"; done; echo '{}' > "$1/out/00_manifest.json"; }
set_of() { memo "$1/explained"; echo "# slides" > "$1/$2-slides.md"; echo "<html></html>" > "$1/$2-slides.html"; }

# 合格：1 件
set_of ok-single report; mkdir -p ok-single/.work/md; echo "# src" > ok-single/.work/md/report.md
# 合格：2 件以上
mkdir -p ok-multi/.work; set_of ok-multi/src__main.py src__main.py; set_of ok-multi/docs__guide.pdf docs__guide.pdf
printf '# 一覧\n- [src__main.py](src__main.py/explained/README.md)\n- [docs__guide.pdf](docs__guide.pdf/explained/README.md)\n' > ok-multi/00_index.md
# 不合格 1：<ID>_explained/ の中にスライド
mkdir bad-explained-suffix; memo bad-explained-suffix/2hlzMVgTIGs_explained
echo "# slides" > bad-explained-suffix/2hlzMVgTIGs_explained/2hlzMVgTIGs-slides.md; echo "<html></html>" > bad-explained-suffix/2hlzMVgTIGs_explained/2hlzMVgTIGs-slides.html
# 不合格 2：<名前>/explain-out/ の入れ子
mkdir -p bad-nested/report; set_of bad-nested/report/explain-out report
# 不合格 3：直下の source.md
cp -R ok-single bad-source-at-top; echo "# src" > bad-source-at-top/source.md
