#!/usr/bin/env python3
"""合格条件 9：lint の error と warn を合わせて 3 件以上仕込んだスライド MD を渡して直させると、
直した後の lint が error 0・warn 0 になる。

- 入力: tests/fixtures/lint/seeded-slides.md（error 1・warn 2 を仕込んだ、M1 の E2E と同じ原稿）
- 直させる: claude -p（有料）で、複製したスキル（ced-websearch-slide-ja）を使わせて直し、結果を保存する
- 確かめる: 直した後の lint（mdss-convert --json-only の lint 配列）が error 0・warn 0

使い方:
  python3 tests/e2e_lint_fix.py before                 # 仕込みの件数を確かめる（無料）
  python3 tests/e2e_lint_fix.py run --out <作業フォルダ>  # 直させる（有料。実行前に承認を得る）
  python3 tests/e2e_lint_fix.py after <直したファイル>     # 直した後の lint を確かめる（無料）
終了コード: 0＝合格、1＝不合格、2＝引数の誤り
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEEDED = REPO / "tests/fixtures/lint/seeded-slides.md"
PLUGIN = REPO / "plugins/ced-skills"


def lint_counts(md: Path):
    out = subprocess.run(["mdss-convert", str(md), "--json-only"], capture_output=True, text=True)
    data = json.loads(out.stdout)
    items = data.get("lint", [])
    return sum(1 for i in items if i.get("level") == "error"), sum(1 for i in items if i.get("level") == "warn"), items


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("before")
    r = sub.add_parser("run")
    r.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("after")
    a.add_argument("fixed", type=Path)
    args = ap.parse_args()

    if args.cmd == "before":
        e, w, items = lint_counts(SEEDED)
        print(f"仕込み: error {e}・warn {w}（合計 {e + w} 件、3 件以上が必要）")
        return 0 if e + w >= 3 else 1

    if args.cmd == "run":
        args.out.mkdir(parents=True, exist_ok=True)
        work = args.out / "slides.md"
        work.write_text(SEEDED.read_text(encoding="utf-8"), encoding="utf-8")
        prompt = (
            f"次のスライド MD の lint 指摘（mdss-convert --json-only の lint 配列の error と warn）をすべて直してください。"
            f"対象: {work}。直したあとの内容を {args.out / 'fixed.md'} に保存してください。"
            "文と数値は変えず、記法と type と frontmatter だけを直すこと。ced-websearch-slide-ja の記法に従うこと。"
            "lint の error と warn が 0 になったことを確かめてから終えること。"
        )
        cmd = [
            "claude", "-p", prompt,
            "--plugin-dir", str(PLUGIN),
            "--output-format", "stream-json", "--verbose",
            "--max-budget-usd", "5",
            "--allowedTools", "Skill Bash Read Write Edit Glob Grep",
        ]
        log = args.out / "stream.jsonl"
        with log.open("w", encoding="utf-8") as f:
            rc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL).returncode
        print(f"claude -p の終了コード: {rc}（記録: {log}）")
        return 0 if rc == 0 else 1

    # after
    if not args.fixed.exists():
        print(f"直したファイルがない: {args.fixed}", file=sys.stderr)
        return 2
    e, w, items = lint_counts(args.fixed)
    ok = e == 0 and w == 0
    print(f"直した後の lint: error {e}・warn {w}")
    for i in items:
        print(" ", i)
    print("PASS: 合格条件 9" if ok else "FAIL: 合格条件 9")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
