#!/usr/bin/env python3
"""合格条件 8：出力フォルダの「形」を確かめる。標準ライブラリのみ。中身の質は見ない（それは check_docs.py と lint の役割）。

形（PLAN.md 4.8）:
  入力 1 件  <出力先>/explained/（5 ファイル＋任意の out/）、<名前>-slides.md と .html が 1 組、任意の .work/
  入力 2 件以上  <出力先>/00_index.md、<スラッグ>/（explained/ と <スラッグ>-slides.md・.html）、任意の .work/
  どちらも、上の他のものが出力先の直下にあれば不合格。判定は、00_index.md の有無で 1 件／2 件以上に分ける。

不合格の形（見本は tests/fixtures/layout/bad-*）:
  <ID>_explained/ という名前のメモのフォルダ、<名前>/explain-out/ の入れ子、直下の source.md などの中間ファイル

使い方: python3 tests/check_output_layout.py <出力フォルダ> [--json]
終了コード: 0＝合格、1＝不合格、2＝フォルダが無い
"""
import argparse
import json
import sys
from pathlib import Path

FINAL_FILES = ("README.md", "01_source.md", "02_explanation_memo.md",
               "11_question_and_answer.md", "12_LLM_prompts_as_guide.md")
INDEX = "00_index.md"
WORK = ".work"
SLIDE_SUFFIX = "-slides"


def check_set(d: Path, rel: str, slide_name):
    """1 つのセット（解説メモ＋スライド）の形を確かめる。d は、そのセットを置く（出力先かスラッグの）フォルダ。"""
    out = []
    docs = d / "explained"
    if not docs.is_dir():
        out.append(f"{rel}explained/ が無い")
    else:
        for f in FINAL_FILES:
            if not (docs / f).is_file():
                out.append(f"{rel}explained/{f} が無い")
        for e in sorted(docs.iterdir()):
            if e.name in FINAL_FILES or (e.name == "out" and e.is_dir()):
                continue
            out.append(f"{rel}explained/{e.name} は置いてはいけない（5 ファイルと out/ だけ）")
    mds = sorted(p for p in d.glob(f"*{SLIDE_SUFFIX}.md"))
    htmls = sorted(p for p in d.glob(f"*{SLIDE_SUFFIX}.html"))
    if len(mds) != 1 or len(htmls) != 1 or (mds and htmls and mds[0].stem != htmls[0].stem):
        out.append(f"{rel}<名前>{SLIDE_SUFFIX}.md と .html が 1 組ではない（md {len(mds)} 件、html {len(htmls)} 件）")
    elif slide_name is not None and mds[0].stem != slide_name + SLIDE_SUFFIX:
        out.append(f"{rel}スライドの名前は {slide_name}{SLIDE_SUFFIX}.md のはず（実際: {mds[0].name}）")
    return out


def check_layout(root: Path):
    problems = []
    entries = sorted(root.iterdir())
    names = {e.name for e in entries}
    # 不合格の形：名前の付いた入れ子や中間ファイルは、どこにあっても不合格
    for p in sorted(root.rglob("*")):
        if WORK in p.relative_to(root).parts:
            continue
        rel = p.relative_to(root).as_posix()
        if p.is_dir() and p.name == "explain-out":
            problems.append(f"{rel}/ は入れ子の出力（explain-out の中に出力がある）")
        if p.is_dir() and p.name.endswith("_explained"):
            problems.append(f"{rel}/ は旧形式のメモのフォルダ（メモは explained/ に置く）")
    if INDEX in names:  # 2 件以上
        slugs = [e for e in entries if e.is_dir() and e.name not in ("explained", WORK)]
        if "explained" in names:
            problems.append("2 件以上の形なのに、直下に explained/ がある")
        if len(slugs) < 2:
            problems.append(f"{INDEX} があるのに、スラッグのフォルダが {len(slugs)} 件（2 件以上のはず）")
        index_text = (root / INDEX).read_text(encoding="utf-8", errors="replace")
        for s in slugs:
            problems += check_set(s, f"{s.name}/", s.name)
            if s.name not in index_text:
                problems.append(f"{INDEX} に {s.name} へのリンクが無い")
        for e in entries:
            if e.is_file() and e.name != INDEX:
                problems.append(f"直下に {e.name} がある（置いてよいのは {INDEX} だけ）")
    else:  # 1 件
        problems += check_set(root, "", None)
        for e in entries:
            if e.name in ("explained", WORK):
                continue
            if e.is_file() and e.name.endswith((f"{SLIDE_SUFFIX}.md", f"{SLIDE_SUFFIX}.html")):
                continue
            problems.append(f"直下に {e.name}{'/' if e.is_dir() else ''} がある（置いてよいのは explained/・"
                            f"<名前>{SLIDE_SUFFIX}.md/.html・{WORK}/ だけ）")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not a.out.is_dir():
        print(f"フォルダが無い: {a.out}", file=sys.stderr)
        return 2
    problems = check_layout(a.out)
    if a.json:
        print(json.dumps({"ok": not problems, "problems": problems}, ensure_ascii=False, indent=2))
    else:
        print(f"{'FAIL' if problems else 'PASS'}  出力の形: {a.out}")
        for p in problems:
            print(f"      {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
