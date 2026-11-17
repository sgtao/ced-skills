#!/usr/bin/env python3
"""合格条件 6：explain の質問の扱いを確かめる（静的検査＋E2E の記録）。

静的検査（plugins/ced-skills/commands/explain.md）:
- 質問の定義が 4 問以内（既定で 3 問）、質問文と選択肢があり、質問文が日本語
- AskUserQuestion を呼ぶ指示は、手順 1 の中だけにある
- 引数が 3 つそろったときは AskUserQuestion を呼ばない、と書いてある
- AskUserQuestion が allowed-tools に入っている

E2E の記録（--stream で stream-json を渡したとき）:
- 引数で 3 つの答えを渡した実行では、AskUserQuestion の呼び出しが 0 回

使い方: python3 tests/check_explain.py [--stream tests/e2e-record/m1-html/stream.jsonl]
終了コード: 0＝合格、1＝不合格
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPLAIN = REPO / "plugins/ced-skills/commands/explain.md"


def static_checks(text: str):
    problems = []
    m = re.search(r"^allowed-tools:\s*(.+)$", text, re.M)
    if not m or "AskUserQuestion" not in m.group(1):
        problems.append("allowed-tools に AskUserQuestion がない")

    # 質問の定義（「- Q1 …」形式）を数える
    qs = re.findall(r"^- Q(\d+) ", text, re.M)
    if not qs:
        problems.append("質問の定義（- Q1 ...）がない")
    if len(qs) > 4:
        problems.append(f"質問が {len(qs)} 問（4 問以内）")
    for q in re.finditer(r"^- Q\d+ .*$", text, re.M):
        line = q.group(0)
        if "選択肢:" not in line and "選択肢：" not in line:
            problems.append(f"選択肢がない: {line[:40]}")
        if not re.search(r"[ぁ-んァ-ヶ一-龠]", line):
            problems.append(f"日本語でない: {line[:40]}")

    # AskUserQuestion の指示は手順 1 の中だけにある
    steps = text.split("## 手順", 1)[-1]
    step1 = re.search(r"^### 1\..*?(?=^### 2\.)", steps, re.M | re.S)
    if not step1:
        problems.append("手順 1 が見つからない")
        return problems, len(qs)
    if steps.count("AskUserQuestion") != step1.group(0).count("AskUserQuestion"):
        problems.append("AskUserQuestion の指示が手順 1 の外にある")
    if step1.group(0).count("AskUserQuestion") == 0:
        problems.append("手順 1 に AskUserQuestion の指示がない")
    if "AskUserQuestion を呼ばない" not in step1.group(0):
        problems.append("引数が 3 つそろったときに AskUserQuestion を呼ばない、の記述がない")
    if "1 回の呼び出し" not in step1.group(0):
        problems.append("質問を 1 回にまとめる、の記述がない")
    return problems, len(qs)


def stream_count(path: Path):
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "assistant":
            for c in e.get("message", {}).get("content", []):
                if c.get("type") == "tool_use" and c.get("name") == "AskUserQuestion":
                    n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", type=Path, help="引数で 3 つの答えを渡した E2E の stream-json")
    args = ap.parse_args()
    ok = True
    problems, nq = static_checks(EXPLAIN.read_text(encoding="utf-8"))
    print(f"質問の数（定義）: {nq}（4 問以内）")
    for p in problems:
        print("FAIL:", p)
    ok = ok and not problems
    if args.stream:
        n = stream_count(args.stream)
        print(f"E2E の AskUserQuestion 呼び出し: {n} 回（引数で答えを渡した実行は 0 回）")
        ok = ok and n == 0
    print(("PASS" if ok else "FAIL") + ": explain の質問（静的検査" + ("と E2E の記録" if args.stream else "") + "）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
