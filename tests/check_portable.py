#!/usr/bin/env python3
"""合格条件 9：ced-explain（Claude Code 以外のツール向けの生成物）を確かめる。標準ライブラリのみ。

確かめること:
- 4 スキルと ced-explain の name が、フォルダ名と一致する
- description が 1〜1024 字
- adapters/ced-explain/SKILL.md が、scripts/build_explain_skill.py の生成結果と一致する（手で直していない）
- ced-explain の中に、AskUserQuestion・$ARGUMENTS・allowed-tools・argument-hint・/ced-skills: が無い

使い方: python3 tests/check_portable.py     終了コード: 0＝合格、1＝不合格
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import build_explain_skill as B  # noqa: E402

SKILL_DIRS = ["ced-url-to-md", "ced-pdf-to-md-ja", "ced-craft-explanation-docs", "ced-websearch-slide-ja"]
FORBIDDEN = ["AskUserQuestion", "$ARGUMENTS", "allowed-tools", "argument-hint", "/ced-skills:"]


def frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).split("\n"):
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def problems_for(explain_md: str, adapter_md: str, skill_mds: dict) -> list[str]:
    out = []
    for name, text in skill_mds.items():
        fm = frontmatter(text)
        if fm.get("name") != name:
            out.append(f"{name}: name が フォルダ名と一致しない（{fm.get('name')!r}）")
        desc = fm.get("description", "")
        if not 1 <= len(desc) <= 1024:
            out.append(f"{name}: description が 1〜1024 字でない（{len(desc)} 字）")
    afm = frontmatter(adapter_md)
    if afm.get("name") != "ced-explain":
        out.append(f"ced-explain: name が ced-explain でない（{afm.get('name')!r}）")
    if not 1 <= len(afm.get("description", "")) <= 1024:
        out.append("ced-explain: description が 1〜1024 字でない")
    if set(afm) - {"name", "description"}:
        out.append(f"ced-explain: frontmatter に name・description 以外がある（{sorted(set(afm) - {'name', 'description'})}）")
    expected = B.build(explain_md)
    if adapter_md != expected:
        out.append("ced-explain: adapters/ced-explain/SKILL.md が生成結果と一致しない（手で直した可能性。build_explain_skill.py で作り直す）")
    for word in FORBIDDEN:
        n = adapter_md.count(word)
        if n:
            out.append(f"ced-explain: 禁止した語句が {n} 件ある: {word}")
    return out


def main() -> int:
    explain_md = (REPO / "plugins" / "commands" / "explain.md").read_text(encoding="utf-8")
    adapter_md = (REPO / "adapters" / "ced-explain" / "SKILL.md").read_text(encoding="utf-8")
    skill_mds = {d: (REPO / "plugins" / d / "SKILL.md").read_text(encoding="utf-8") for d in SKILL_DIRS}
    problems = problems_for(explain_md, adapter_md, skill_mds)
    print(f"{'FAIL' if problems else 'PASS'}  ced-explain の検査（条件 9）")
    for p in problems:
        print(f"      {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
