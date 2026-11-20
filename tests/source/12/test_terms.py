"""v0.0.2 M8（B3・B6）：toTopPage の飛び先、英語の見出し、「解説メモ」の用語。

- 1 行目の toTopPage は ./README.md（作業フォルダの中の README）を指す
- 見出しは日本語にそろえる（英語の見出しを使わない。ファイル名の LLM_prompts に合わせて「LLM 用プロンプト」）
- 「解説メモ」は、5 ファイルの一式か、02_explanation_memo.md の 1 つか、どちらかを用語表で決める
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "plugins" / "ced-craft-explanation-docs"  # スキルのフォルダ
SKIP_DIRS = {"dist", ".git", "__pycache__", ".pytest_cache"}


def _texts(exclude_tests=True):
    for p in ROOT.rglob("*"):
        if not p.is_file() or set(p.relative_to(ROOT).parts) & SKIP_DIRS:
            continue
        if exclude_tests and p.relative_to(ROOT).parts[0] == "tests":
            continue
        if p.suffix in (".md", ".py", ".json", ".txt", ".sh"):
            yield p, p.read_text(encoding="utf-8", errors="replace")


def test_no_top_page_link_points_outside_the_work_folder():
    """ナビの toTopPage は、どのファイルでも ../README.md を指さない（テストの見本を除く）。"""
    bad = [str(p.relative_to(ROOT)) for p, t in _texts() if "[toTopPage](" + "../README.md)" in t]
    assert bad == []


def test_no_english_proposed_prompts_heading():
    bad = [str(p.relative_to(ROOT)) for p, t in _texts() if ("Proposed" + " Prompts") in t]
    assert bad == []


def test_terms_table_defines_both_meanings():
    text = (ROOT / "references" / "output-formats.md").read_text(encoding="utf-8")
    assert "解説メモ一式" in text and "02_explanation_memo.md" in text
    assert re.search(r"\|\s*解説メモ一式\s*\|", text), "用語の表に「解説メモ一式」が無い"
    assert re.search(r"\|\s*解説メモ\s*\|", text), "用語の表に「解説メモ」が無い"


def test_completion_report_says_the_set():
    text = (ROOT / "references" / "output-formats.md").read_text(encoding="utf-8")
    assert "解説メモ一式を作りました。" in text
    assert "解説メモを作りました。" not in text
