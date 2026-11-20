#!/usr/bin/env python3
"""1 組のスライド md の見た目の多様さを数える（合格条件 4）。

- 型：`points`・`table` 以外の型が 2 種以上あるか
- 区切り：`tone: dark` の指定が 1 つ以上あるか
- 強調：`==強調==` が 1 つ以上あるか

簡素に見えたスライド（points と table だけの白地）は、いずれかで不合格になる。

使い方: python3 tests/check_slide_variety.py <スライド.md>
終了コード: 0＝合格、1＝不合格、2＝引数の誤り
"""
import re
import sys
from pathlib import Path

PLAIN_TYPES = {"points", "table"}
TYPE_RE = re.compile(r"<!--\s*slide:\s*([a-z][a-z-]*)")


def count(md_text):
    types = TYPE_RE.findall(md_text)
    other = sorted({t for t in types if t not in PLAIN_TYPES})
    return {
        "types": sorted(set(types)),
        "other_types": other,
        "dark": len(re.findall(r"tone:\s*dark", md_text)),
        "emphasis": len(re.findall(r"==[^=\n]+==", md_text)),
    }


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not Path(args[0]).is_file():
        print("使い方: python3 tests/check_slide_variety.py <スライド.md>", file=sys.stderr)
        return 2
    c = count(Path(args[0]).read_text(encoding="utf-8"))
    problems = []
    if len(c["other_types"]) < 2:
        problems.append(f"points・table 以外の型が {len(c['other_types'])} 種（2 種以上が必要）")
    if c["dark"] < 1:
        problems.append("tone: dark の区切りが無い")
    if c["emphasis"] < 1:
        problems.append("==強調== が無い")
    print(f"型: {', '.join(c['types']) or 'なし'}（points・table 以外 {len(c['other_types'])} 種）")
    print(f"tone: dark {c['dark']} 件／強調 {c['emphasis']} 件")
    if problems:
        print("FAIL: " + "；".join(problems))
        return 1
    print("PASS: 型・区切り・強調がそろっている")
    return 0


if __name__ == "__main__":
    sys.exit(main())
