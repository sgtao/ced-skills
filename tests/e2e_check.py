#!/usr/bin/env python3
"""E2E の出力を確かめる（合格条件 7・8）。

7. 解説メモ 5 本（README.md・01_source.md・02_explanation_memo.md・11_question_and_answer.md・
   12_LLM_prompts_as_guide.md）が、craft-explanation-docs の check_docs.py に合格する。
   スライドの .md と .html が 1 組ある。
8. スライド MD を mdss-convert --json-only にかけ、lint の error 0・warn 0。
9. 出力の形が固定の形に合う（v0.0.2。tests/check_output_layout.py。--skip-layout で外せる）。

使い方:
  python3 tests/e2e_check.py <E2E の出力フォルダ> [--json] [--skip-layout]
終了コード: 0＝合格、1＝不合格、2＝出力が見つからない。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_output_layout import check_layout  # noqa: E402
CHECK_DOCS = (REPO / "plugins/ced-craft-explanation-docs/scripts/check_docs.py")
FINAL_FILES = [
    "README.md",
    "01_source.md",
    "02_explanation_memo.md",
    "11_question_and_answer.md",
    "12_LLM_prompts_as_guide.md",
]


def find_docs_folder(root: Path):
    hits = [p.parent for p in root.rglob("02_explanation_memo.md")]
    hits = [h for h in hits if all((h / f).exists() for f in FINAL_FILES)]
    return hits


def find_slide_pairs(root: Path, docs_folder):
    pairs, orphans = [], []
    for md in sorted(root.rglob("*.md")):
        # 解説メモの 5 本、作業フォルダ（00_manifest.json がある階層）と .work は、スライドではない
        if md.name in FINAL_FILES or ".work" in md.parts:
            continue
        if any((anc / "00_manifest.json").exists() for anc in [md.parent, *md.parents] if root in [anc, *anc.parents]):
            continue
        if "/skills/" in str(md):
            continue
        # url-to-md の変換結果（入力の Markdown）は、スライドではない
        if md.read_text(encoding="utf-8", errors="replace").lstrip().startswith("---") and "source_format:" in md.read_text(encoding="utf-8", errors="replace")[:600]:
            continue
        html = md.with_suffix(".html")
        if html.exists():
            pairs.append((md, html))
        else:
            orphans.append(md)
    return pairs, orphans


def lint(md: Path):
    out = subprocess.run(["mdss-convert", str(md), "--json-only"], capture_output=True, text=True)
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return None, out.stderr.strip() or out.stdout.strip()
    items = data.get("lint", [])
    errors = sum(1 for i in items if i.get("level") == "error")
    warns = sum(1 for i in items if i.get("level") == "warn")
    return {"error": errors, "warn": warns, "items": items}, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path, help="E2E の出力フォルダ")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--skip-layout", action="store_true", help="出力の形の検査を外す（v0.0.1 の記録用）")
    args = ap.parse_args()
    report = {"criteria": {}, "details": {}}
    root = args.out
    if not root.is_dir():
        print(f"output not found: {root}", file=sys.stderr)
        return 2

    docs = find_docs_folder(root)
    if len(docs) != 1:
        print(f"FAIL: docs folder with the 5 files: found {len(docs)}", file=sys.stderr)
        report["criteria"]["7_docs_folder"] = False
        pairs, orphans = [], []
        docs_folder = None
    else:
        docs_folder = docs[0]
        report["criteria"]["7_docs_folder"] = True
        # explain は out/ を .work/out/ へ移すので、その場所を渡す（無ければ既定の out/）
        out_dir = docs_folder / ".work" / "out"
        extra = ["--out-dir", str(out_dir)] if out_dir.is_dir() else []
        r = subprocess.run([sys.executable, str(CHECK_DOCS), str(docs_folder), *extra, "--json"],
                           capture_output=True, text=True)
        report["details"]["check_docs_exit"] = r.returncode
        report["criteria"]["7_check_docs"] = r.returncode == 0
        report["details"]["check_docs_out"] = r.stdout[-2000:]
        pairs, orphans = find_slide_pairs(root, docs_folder)

    report["criteria"]["7_slide_pair"] = len(pairs) == 1 and not orphans
    report["details"]["slide_pairs"] = [[str(m), str(h)] for m, h in pairs]
    report["details"]["slide_orphans"] = [str(o) for o in orphans]

    if len(pairs) == 1:
        md, _ = pairs[0]
        res, err = lint(md)
        if res is None:
            report["criteria"]["8_lint_zero"] = False
            report["details"]["lint_error"] = err
        else:
            report["criteria"]["8_lint_zero"] = res["error"] == 0 and res["warn"] == 0
            report["details"]["lint"] = {"error": res["error"], "warn": res["warn"], "items": res["items"]}
    else:
        report["criteria"]["8_lint_zero"] = False

    if not args.skip_layout:
        problems = check_layout(root)
        report["criteria"]["9_layout"] = not problems
        report["details"]["layout_problems"] = problems

    ok = all(report["criteria"].values())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for k, v in report["criteria"].items():
            print(f"{'PASS' if v else 'FAIL'}  {k}")
        for p in report["details"].get("layout_problems", []):
            print(f"      形: {p}")
        if "lint" in report["details"]:
            print(f"lint: error={report['details']['lint']['error']} warn={report['details']['lint']['warn']}")
        print("PASS: E2E 7・8" if ok else "FAIL: E2E 7・8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
