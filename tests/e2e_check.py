#!/usr/bin/env python3
"""E2E の出力を確かめる（合格条件 7・8・9）。

1 件の出力（作業フォルダの直下に解説メモ 5 本）と、2 件以上の出力（直下に 00_index.md と子のフォルダ）の両方に対応する。
2 件以上のときは、子のフォルダごとに 7・8 を確かめ、基準の名前は「<子の名前>/<基準>」になる。

7. 解説メモ 5 本（README.md・01_source.md・02_explanation_memo.md・11_question_and_answer.md・
   12_LLM_prompts_as_guide.md）が、craft-explanation-docs の check_docs.py に合格する。
   スライドの .md と .html が 1 組ある。
   2 件以上のとき、子の数が 2 以上（7_units）。
8. スライド MD を mdss-convert --json-only にかけ、lint の error 0・warn 0。
9. 出力の形が固定の形に合う（v0.0.3 の形。tests/check_output_layout.py。--skip-layout で外せる）。

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


def is_multi(root: Path) -> bool:
    """2 件以上の出力（直下に 00_index.md）か。"""
    return (root / "00_index.md").is_file()


def units_of(root: Path):
    """確かめる単位。1 件なら作業フォルダそのもの、2 件以上なら直下の子のフォルダ（.work を除く）。"""
    if not is_multi(root):
        return [root]
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name != ".work")


def check_unit(unit: Path, prefix: str, report: dict):
    """1 件分の 7・8 を確かめ、report に prefix 付きで書く。"""
    crit, det = report["criteria"], report["details"]
    docs = find_docs_folder(unit)
    if len(docs) != 1:
        crit[prefix + "7_docs_folder"] = False
        pairs, orphans = [], []
    else:
        docs_folder = docs[0]
        crit[prefix + "7_docs_folder"] = True
        # explain は out/ を .work/out/ へ移すので、その場所を渡す（無ければ既定の out/）
        out_dir = docs_folder / ".work" / "out"
        extra = ["--out-dir", str(out_dir)] if out_dir.is_dir() else []
        r = subprocess.run([sys.executable, str(CHECK_DOCS), str(docs_folder), *extra, "--json"],
                           capture_output=True, text=True)
        det[prefix + "check_docs_exit"] = r.returncode
        crit[prefix + "7_check_docs"] = r.returncode == 0
        det[prefix + "check_docs_out"] = r.stdout[-2000:]
        pairs, orphans = find_slide_pairs(unit, docs_folder)

    crit[prefix + "7_slide_pair"] = len(pairs) == 1 and not orphans
    det[prefix + "slide_pairs"] = [[str(m), str(h)] for m, h in pairs]
    det[prefix + "slide_orphans"] = [str(o) for o in orphans]

    if len(pairs) == 1:
        md, _ = pairs[0]
        res, err = lint(md)
        if res is None:
            crit[prefix + "8_lint_zero"] = False
            det[prefix + "lint_error"] = err
        else:
            crit[prefix + "8_lint_zero"] = res["error"] == 0 and res["warn"] == 0
            det[prefix + "lint"] = {"error": res["error"], "warn": res["warn"], "items": res["items"]}
    else:
        crit[prefix + "8_lint_zero"] = False


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

    multi = is_multi(root)
    if multi:
        units = units_of(root)
        report["criteria"]["7_units"] = len(units) >= 2
        report["details"]["units"] = [u.name for u in units]
    for unit in units_of(root):
        prefix = f"{unit.name}/" if multi else ""
        check_unit(unit, prefix, report)

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
        for k, v in report["details"].items():
            if k.endswith("lint") and isinstance(v, dict):
                print(f"lint {k}: error={v['error']} warn={v['warn']}")
        print("PASS: E2E 7・8" if ok else "FAIL: E2E 7・8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
