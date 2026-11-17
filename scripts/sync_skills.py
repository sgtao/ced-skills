#!/usr/bin/env python3
"""01_sources の 4 スキルを plugins/ced-skills/skills/ に複製し、名前に ced- を付ける。

- 置き換えは、フォルダ名・SKILL.md の name:・Markdown（.md）の中の 4 スキル名だけ。
  前後が英数字かハイフンなら置き換えない（url-to-md が ced-url-to-md の一部になるのを防ぐ）。
- .py・.sh・.json などは中身を変えない。
- 複製のあとに sources.lock.json に、元と複製のハッシュを書く。

使い方（リポジトリのトップから）:
  python3 scripts/sync_skills.py             # 複製し直す
  python3 scripts/sync_skills.py --check     # 元に置き換えを当てた結果と、複製が一致するか確かめる
  python3 scripts/sync_skills.py --list      # 置き換えた箇所を一覧する
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = REPO.parents[1] / "01_sources"
DEST = REPO / "plugins" / "ced-skills" / "skills"
LOCK = REPO / "sources.lock.json"

# 元の名前 -> 01_sources の中の場所
SKILLS = {
    "url-to-md": "11_dev-skill-web-to-markdown-ja/url-to-md",
    "pdf-to-md-ja": "11_dev-skill-web-to-markdown-ja/pdf-to-md-ja",
    "craft-explanation-docs": "12_dev-skill-craft-explanation-docs/craft-explanation-docs",
    "websearch-slide-ja": "13_dev-skill-websearch-slide-ja/websearch-slide-ja",
}
PREFIX = "ced-"
NAME_RE = re.compile(
    r"(?<![A-Za-z0-9-])(" + "|".join(re.escape(n) for n in SKILLS) + r")(?![A-Za-z0-9-])"
)
SKIP_DIRS = {"__pycache__", ".venv", ".pytest_cache", "dist", "node_modules", ".git"}
SKIP_FILES = {".DS_Store"}


def files_of(root: Path):
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts) or p.name in SKIP_FILES:
            continue
        if p.is_file():
            yield rel


def transform_text(text: str) -> tuple[str, int]:
    return NAME_RE.subn(lambda m: PREFIX + m.group(1), text)


def transform_bytes(rel: Path, data: bytes) -> tuple[bytes, int]:
    if rel.suffix != ".md":
        return data, 0
    text, n = transform_text(data.decode("utf-8"))
    return text.encode("utf-8"), n


def build_expected(source_root: Path, name: str):
    """元のフォルダに置き換えを当てた結果を、{複製の相対パス: (bytes, 置き換え数)} で返す。"""
    out = {}
    src = source_root / SKILLS[name]
    for rel in files_of(src):
        data, n = transform_bytes(rel, (src / rel).read_bytes())
        out[rel] = (data, n, (src / rel).read_bytes())
    return out


def dest_name(name: str) -> str:
    return PREFIX + name


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sync(source_root: Path) -> int:
    lock = {"sources": str(source_root.name), "skills": {}}
    if DEST.exists():
        for child in DEST.iterdir():
            if child.is_dir() and child.name.startswith(PREFIX):
                shutil.rmtree(child)
    DEST.mkdir(parents=True, exist_ok=True)
    for name in SKILLS:
        expected = build_expected(source_root, name)
        target = DEST / dest_name(name)
        files = {}
        total = 0
        for rel, (data, n, orig) in expected.items():
            p = target / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            total += n
            files[str(rel)] = {"orig_sha256": sha(orig), "out_sha256": sha(data), "replacements": n}
        lock["skills"][dest_name(name)] = {"source": SKILLS[name], "files": files, "replacements": total}
        print(f"copied {dest_name(name)}: {len(files)} files, {total} replacements")
    LOCK.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


def check(source_root: Path) -> int:
    problems = []
    for name in SKILLS:
        expected = build_expected(source_root, name)
        target = DEST / dest_name(name)
        actual = set(files_of(target)) if target.exists() else set()
        if actual != set(expected):
            problems.append(f"{dest_name(name)}: file set differs (missing {sorted(map(str, set(expected) - actual))}, extra {sorted(map(str, actual - set(expected)))})")
        for rel, (data, _n, _orig) in expected.items():
            p = target / rel
            if p.exists() and p.read_bytes() != data:
                problems.append(f"{dest_name(name)}/{rel}: differs from transform(source)")
        # 2 回かけても変わらない（冪等）
        for rel, (data, _n, _orig) in expected.items():
            again, _ = transform_bytes(rel, data)
            if again != data:
                problems.append(f"{dest_name(name)}/{rel}: transform is not idempotent")
        # 元の名前が単独で残っていないか（.md）
        for rel in actual:
            if rel.suffix == ".md":
                text = (target / rel).read_text(encoding="utf-8")
                for m in NAME_RE.finditer(text):
                    problems.append(f"{dest_name(name)}/{rel}: bare name left: {m.group(1)}")
        # SKILL.md の name: が ced- 付きか
        skill_md = target / "SKILL.md"
        if skill_md.exists():
            m = re.search(r"^name:\s*(\S+)\s*$", skill_md.read_text(encoding="utf-8"), re.M)
            if not m or m.group(1) != dest_name(name):
                problems.append(f"{dest_name(name)}/SKILL.md: name is {m.group(1) if m else None}")
        else:
            problems.append(f"{dest_name(name)}: SKILL.md missing")
    if problems:
        print("FAIL")
        for p in problems:
            print("  -", p)
        return 1
    print(f"PASS: {len(SKILLS)} skills match transform(source); no bare names in .md")
    return 0


def list_replacements(source_root: Path) -> int:
    for name in SKILLS:
        src = source_root / SKILLS[name]
        for rel in files_of(src):
            if rel.suffix != ".md":
                continue
            text = (src / rel).read_text(encoding="utf-8")
            for i, line in enumerate(text.splitlines(), 1):
                for m in NAME_RE.finditer(line):
                    print(f"{dest_name(name)}/{rel}:{i}: {m.group(1)} -> {PREFIX + m.group(1)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", type=Path, default=DEFAULT_SOURCES, help="01_sources のパス")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true")
    g.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if not args.sources.is_dir():
        print(f"sources not found: {args.sources}", file=sys.stderr)
        return 2
    if args.check:
        return check(args.sources)
    if args.list:
        return list_replacements(args.sources)
    return sync(args.sources)


if __name__ == "__main__":
    sys.exit(main())
