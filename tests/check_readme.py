#!/usr/bin/env python3
"""合格条件 10：README の記述を確かめる。標準ライブラリのみ。

検査項目（--only で絞れる。マイルストーンごとに満たす項目が増える）:
  stale   古い字幕の注意（英語の YouTube で字幕が取れない、という記述）が 0 件（M1）
  inputs  入力の種類の一覧がある（URL・PDF・Office・HTML・YouTube・テキスト・コード・フォルダ・ZIP）（M5）
  targets Claude Code と 4 ツールの対応表があり、「配置を検査済み」「実機で確認済み」の列がある（M7）
  structure 開発者向けの「ファイル構成」と「テスト」の節が、実在する主なファイル・検査を載せている（M8 後の見直し）

使い方: python3 tests/check_readme.py [--only stale[,inputs,targets]] [--readme <パス>]
終了コード: 0＝合格、1＝不合格
"""
import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ITEMS = ("stale", "inputs", "targets", "structure")
INPUT_KINDS = ("URL", "PDF", "Word", "Excel", "PowerPoint", "HTML", "YouTube", "テキスト", "コード", "フォルダ", "ZIP")
TOOLS = ("Claude Code", "Codex", "Copilot", "Gemini CLI", "Antigravity")


def check_stale(text: str):
    """「英語の YouTube」と「字幕が取れず」が同じ行にある記述は、修正済みの不具合の古い注意（e65da12 で修正）。"""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if re.search(r"英語の\s*YouTube", line) and "字幕が取れ" in line:
            out.append(f"{n} 行目: 古い字幕の注意が残っている: {line.strip()[:50]}")
    return out


def table_rows(text: str):
    """Markdown の表の行（| で始まる行）を、セルの配列にして返す。区切りの行（|---|）は除く。"""
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and not re.fullmatch(r"\|[\s:|-]+\|?", s):
            rows.append([c.strip() for c in s.strip("|").split("|")])
    return rows


def check_inputs(text: str):
    # 見出しの行は 1 行に限る（DOTALL の .* が改行をまたいで、別の見出しに当たらないように）
    m = re.search(r"^#{2,3} [^\n]*入力[^\n]*$(.*?)(?=^#{1,3} |\Z)", text, re.M | re.S)
    if not m:
        return ["入力の種類の一覧の節（「入力」を含む見出し）が無い"]
    body = m.group(1)
    missing = [k for k in INPUT_KINDS if k not in body]
    return [f"入力の種類の一覧に載っていない: {', '.join(missing)}"] if missing else []


def check_targets(text: str):
    rows = table_rows(text)
    head = next((r for r in rows if any("配置を検査済み" in c for c in r) and any("実機で確認済み" in c for c in r)), None)
    if head is None:
        return ["「配置を検査済み」「実機で確認済み」の列を持つ対応表が無い"]
    body = "\n".join(" | ".join(r) for r in rows)
    missing = [t for t in TOOLS if t not in body]
    return [f"対応表に載っていないツール: {', '.join(missing)}"] if missing else []


# README の開発者向けの節に載せるもの（実在するものだけを書く。無ければ載せない）
LISTED = [
    "adapters/", "scripts/install.sh", "scripts/sync_skills.py", "scripts/build_explain_skill.py",
    "tests/check_portable.py", "tests/check_readme.py", "tests/check_output_layout.py",
    "tests/check_explain.py", "tests/test_install.py",
]


def check_structure(text: str):
    out = []
    for rel in LISTED:
        if not (REPO / rel).exists():
            out.append(f"{rel} が実在しない（LISTED を直す）")
        elif rel not in text:
            out.append(f"README に {rel} が載っていない")
    return out


CHECKS = {"stale": check_stale, "inputs": check_inputs, "targets": check_targets, "structure": check_structure}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="カンマ区切り。既定は全項目")
    ap.add_argument("--readme", default=str(REPO / "README.md"))
    a = ap.parse_args()
    names = a.only.split(",") if a.only else list(ITEMS)
    bad = [n for n in names if n not in CHECKS]
    if bad:
        print(f"不明な項目: {', '.join(bad)}（{'/'.join(ITEMS)}）", file=sys.stderr)
        return 2
    text = Path(a.readme).read_text(encoding="utf-8")
    fails = 0
    for n in names:
        problems = CHECKS[n](text)
        print(f"{'FAIL' if problems else 'PASS'}  {n}")
        for p in problems:
            print(f"      {p}")
        fails += bool(problems)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
