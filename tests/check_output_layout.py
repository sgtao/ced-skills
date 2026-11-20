#!/usr/bin/env python3
"""合格条件 9：出力フォルダの「形」を確かめる（v0.0.3 の形）。標準ライブラリのみ。中身の質は見ない（それは check_docs.py と lint の役割）。

形（PLAN.md 4.2・D13・D14）:
  入力 1 件  <出力先>/ が YYMMDD_<名前>/ という名前で、直下に解説メモの 5 ファイル、docs/ に
             <名前>-slides.md と .html が 1 組（名前は日付を除く）、任意の .work/（隠し）。それ以外は置かない。
  入力 2 件以上  <出力先>/ が YYMMDD_<名前>/ で、直下は 00_index.md と、子のフォルダ（<子の名前>/）だけ。
             子のフォルダは、1 件のときと同じ形（子の名前は日付を付けない）。任意の .work/。

名前の決まり（D13）: `YYMMDD_<英小文字と数字と ->`、`_` の後ろは 40 文字以内。

不合格の形（見本は tests/fixtures/layout/bad-*）:
  v0.0.2 の形（explained/・explain-out/・<ID>_explained/・直下のスライド）、日付の無い名前、40 文字を超える名前、
  docs/ の外のスライド、直下の中間ファイル。

使い方: python3 tests/check_output_layout.py <出力フォルダ> [--json]
終了コード: 0＝合格、1＝不合格、2＝フォルダが無い
"""
import argparse
import json
import re
import sys
from pathlib import Path

FINAL_FILES = ("README.md", "01_source.md", "02_explanation_memo.md",
               "11_question_and_answer.md", "12_LLM_prompts_as_guide.md")
INDEX = "00_index.md"
WORK = ".work"
DOCS = "docs"
SLIDE_SUFFIX = "-slides"
DATED_RE = re.compile(r"^[0-9]{6}_([a-z0-9]+(?:-[a-z0-9]+)*)$")
PLAIN_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_BODY = 40
OLD_SHAPE_DIRS = ("explained", "explain-out")


def name_problems(name: str, dated: bool):
    """フォルダ名の決まり。dated なら YYMMDD_ を付ける。"""
    if dated:
        m = DATED_RE.match(name)
        if not m:
            return [f"{name}/ の名前が YYMMDD_<英小文字と数字と -> の形ではない"]
        body = m.group(1)
    else:
        if not PLAIN_RE.match(name):
            return [f"{name}/ の名前が英小文字と数字と - だけの形ではない"]
        body = name
    if len(body) > MAX_BODY:
        return [f"{name}/ の名前が 40 文字を超えている（{len(body)} 字）"]
    return []


def check_set(d: Path, rel: str, body: str):
    """1 つのセット（解説メモ 5 ファイル＋docs/ のスライド）の形を確かめる。d は、そのセットのフォルダ。"""
    out = []
    for f in FINAL_FILES:
        if not (d / f).is_file():
            out.append(f"{rel}{f} が無い")
    for e in sorted(d.iterdir()):
        if e.name == WORK or e.name in FINAL_FILES:
            continue
        if e.name == DOCS and e.is_dir():
            continue
        if e.name in OLD_SHAPE_DIRS and e.is_dir():
            out.append(f"{rel}{e.name}/ は v0.0.2 の形（解説メモは直下に置く）")
        elif e.is_dir():
            out.append(f"{rel}{e.name}/ は置いてはいけない（直下に置いてよいのは 5 ファイル、docs/、.work/）")
        else:
            out.append(f"{rel}{e.name} は置いてはいけない（直下に置いてよいのは 5 ファイル、docs/、.work/）")
    docs = d / DOCS
    if not docs.is_dir():
        out.append(f"{rel}{DOCS}/ が無い")
        return out
    mds = sorted(docs.glob(f"*{SLIDE_SUFFIX}.md"))
    htmls = sorted(docs.glob(f"*{SLIDE_SUFFIX}.html"))
    for e in sorted(docs.iterdir()):
        if e.suffix not in (".md", ".html") or not e.name.endswith(f"{SLIDE_SUFFIX}{e.suffix}"):
            out.append(f"{rel}{DOCS}/{e.name} は置いてはいけない（置いてよいのは <名前>{SLIDE_SUFFIX}.md/.html）")
    if len(mds) != 1 or len(htmls) != 1 or mds[0].stem != htmls[0].stem:
        out.append(f"{rel}{DOCS}/ に <名前>{SLIDE_SUFFIX}.md と .html が 1 組ではない（md {len(mds)} 件、html {len(htmls)} 件）")
    elif mds[0].stem != body + SLIDE_SUFFIX:
        out.append(f"{rel}{DOCS}/ のスライドの名前は {body}{SLIDE_SUFFIX}.md のはず（実際: {mds[0].name}）")
    return out


def check_layout(root: Path):
    problems = []
    entries = sorted(root.iterdir())
    names = {e.name for e in entries}
    # 旧い形の目印は、どこにあっても不合格（見本の v0.0.2 の出力）
    for p in sorted(root.rglob("*")):
        if WORK in p.relative_to(root).parts:
            continue
        rel = p.relative_to(root).as_posix()
        if p.is_dir() and p.name == "explain-out":
            problems.append(f"{rel}/ は v0.0.2 の入れ子（explain-out）")
        if p.is_dir() and p.name.endswith("_explained"):
            problems.append(f"{rel}/ は v0.0.2 の形のメモのフォルダ（<ID>_explained）")
    problems += name_problems(root.name, dated=True)
    if INDEX in names:  # 2 件以上
        children = [e for e in entries if e.is_dir() and e.name not in (WORK,)]
        if len(children) < 2:
            problems.append(f"{INDEX} があるのに、子のフォルダが {len(children)} 件（2 件以上のはず）")
        index_text = (root / INDEX).read_text(encoding="utf-8", errors="replace")
        for target in re.findall(r"\]\(([^)\s]+)\)", index_text):
            if target.startswith(("http://", "https://", "#")):
                continue
            if not (root / target).exists():
                problems.append(f"{INDEX} のリンク先が無い: {target}")
        for c in children:
            problems += name_problems(c.name, dated=False)
            problems += check_set(c, f"{c.name}/", c.name)
            if c.name not in index_text:
                problems.append(f"{INDEX} に {c.name} へのリンクが無い")
        for e in entries:
            if e.is_file() and e.name != INDEX:
                problems.append(f"直下に {e.name} がある（置いてよいのは {INDEX} と子のフォルダだけ）")
    else:  # 1 件
        body = root.name.split("_", 1)[1] if DATED_RE.match(root.name) else root.name
        problems += check_set(root, "", body)
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
