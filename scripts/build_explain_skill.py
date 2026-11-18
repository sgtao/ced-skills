#!/usr/bin/env python3
"""plugins/commands/explain.md から、Claude Code 以外のツール向けの ced-explain スキルを生成する。

生成先: adapters/ced-explain/SKILL.md（手で直さない。直すのは explain.md の側）

変換（PLAN 6 節の表）:
- frontmatter の argument-hint・allowed-tools を削除し、name: ced-explain と description を残す
- $ARGUMENTS → 「ユーザーの依頼文に書かれた入力と指定」
- /ced-skills:explain → ced-explain
- AskUserQuestion → 「選択式の質問の手段」（本文の先頭に、質問の仕方を 1 文で書く）

使い方:
  python3 scripts/build_explain_skill.py            # adapters/ced-explain/SKILL.md を書く
  python3 scripts/build_explain_skill.py --check    # 書かずに、今のファイルが生成結果と一致するか確かめる（不一致は 1）
"""
import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "plugins" / "commands" / "explain.md"
OUT = REPO / "adapters" / "ced-explain" / "SKILL.md"

NOTICE = ("<!-- 生成物：scripts/build_explain_skill.py が plugins/commands/explain.md から作る。"
          "手で直さない（直すのは explain.md の側） -->")
ASK_HOWTO = ("質問するときは、選択式の質問の手段があればそれを使い、無ければ番号付きの選択肢を本文に書いて、"
             "返答を待つ。")


def build(explain_md: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", explain_md, re.S)
    if not m:
        raise SystemExit("explain.md に frontmatter が無い")
    fm_lines = m.group(1).split("\n")
    body = explain_md[m.end():]
    desc = next((ln.split(":", 1)[1].strip() for ln in fm_lines if ln.startswith("description:")), None)
    if not desc:
        raise SystemExit("explain.md に description が無い")
    body = body.replace("$ARGUMENTS", "ユーザーの依頼文に書かれた入力と指定")
    body = body.replace("/ced-skills:explain", "ced-explain")
    # 助詞をつけて、「手段 を」のような空白を残さない
    for before, after in (("AskUserQuestion を", "選択式の質問の手段を"), ("AskUserQuestion の", "選択式の質問の手段の"),
                          ("AskUserQuestion", "選択式の質問の手段")):
        body = body.replace(before, after)
    body = body.lstrip("\n")
    return (
        "---\n"
        "name: ced-explain\n"
        f"description: {desc}\n"
        "---\n\n"
        f"{NOTICE}\n\n"
        f"{ASK_HOWTO}\n\n"
        f"{body}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="書かずに、一致を確かめる")
    a = ap.parse_args()
    text = build(SRC.read_text(encoding="utf-8"))
    if a.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("FAIL: adapters/ced-explain/SKILL.md が生成結果と一致しない（build_explain_skill.py で作り直す）", file=sys.stderr)
            return 1
        print("PASS: adapters/ced-explain/SKILL.md は生成結果と一致する")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
