#!/usr/bin/env python3
"""スライドの md の本文が、作られた html の文字に残っているかを確かめる（合格条件 4）。

`sources` 型でリンク以外の行が消える件（mdss-convert の描画）を見つけるための検査。
見出し・lead・point・note・箇条・表のセル・badge と、フェンス内の title／desc／label を
本文の行として数え、html の見える文字（script・style を除く）に、空白と記号の装飾を除いた形で残っているかを見る。

使い方: python3 tests/check_slide_render.py --md <スライド.md> --html <スライド.html>
終了コード: 0＝合格、1＝不合格（残っていない行を出す）、2＝引数の誤り
"""
import argparse
import html as htmllib
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

DIRECTIVE_TEXT = {"lead", "point", "note", "subtitle"}
FENCE_TEXT = {"title", "desc", "label", "name"}


class VisibleText(HTMLParser):
    SKIP = {"script", "style", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            self.parts.append(data)


def squash(s):
    """装飾（Markdown の記号・リンクの URL・空白）を除いて比べる形にする。"""
    s = re.sub(r"<br\s*/?>", "", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = s.replace("**", "").replace("==", "").replace("`", "")
    s = re.sub(r"\s+", "", s)
    return s


def body_lines(md_text):
    """本文の行を返す（frontmatter・区切り線・コメント・フェンスの記法行は除く）。"""
    lines = md_text.splitlines()
    out = []
    i = 0
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            i += 1
        i += 1
    in_fence = False
    for line in lines[i:]:
        s = line.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            m = re.match(r"^\s*([a-z]+):\s*(.+)$", line)
            if m and m.group(1) in FENCE_TEXT:
                out.append(m.group(2).strip().strip('"'))
            continue
        if not s or s == "---" or s.startswith("<!--"):
            continue
        if re.match(r"^\|[\s:|-]+\|$", s):
            continue
        if s.startswith("|") and s.endswith("|"):
            out.extend(c.strip() for c in s.strip("|").split("|") if c.strip())
            continue
        m = re.match(r"^([a-z]+):\s*(.*)$", s)
        if m:
            key, val = m.group(1), m.group(2)
            if key == "badges":
                out.extend(v.strip() for v in val.strip("[]").split(",") if v.strip())
            elif key in DIRECTIVE_TEXT or key == "badge":
                out.append(val)
            continue
        s = re.sub(r"^#+\s*", "", s)
        s = re.sub(r"^>\s*", "", s)
        s = re.sub(r"^(?:[-*]|\d+\.)\s+", "", s)
        out.append(s)
    return [x for x in out if x.strip()]


def check(md_path, html_path):
    md_text = Path(md_path).read_text(encoding="utf-8")
    parser = VisibleText()
    parser.feed(Path(html_path).read_text(encoding="utf-8"))
    visible = re.sub(r"\s+", "", "".join(parser.parts))
    missing = []
    lines = body_lines(md_text)
    for line in lines:
        needle = squash(line)
        if needle and needle not in visible:
            missing.append(line)
    return lines, missing


def main(argv=None):
    ap = argparse.ArgumentParser(description="スライドの本文が html に残っているかを確かめる")
    ap.add_argument("--md", required=True)
    ap.add_argument("--html", required=True)
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    if not Path(a.md).is_file() or not Path(a.html).is_file():
        print("FAIL: md または html が見つからない", file=sys.stderr)
        return 2
    lines, missing = check(a.md, a.html)
    if missing:
        print(f"FAIL: 本文 {len(lines)} 行のうち {len(missing)} 行が html に残っていない")
        for m in missing[:30]:
            print(f"  - {m}")
        return 1
    print(f"PASS: 本文 {len(lines)} 行がすべて html に残っている")
    return 0


if __name__ == "__main__":
    sys.exit(main())
