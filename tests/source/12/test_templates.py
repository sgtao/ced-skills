"""assets/templates/ と references/output-formats.md の整合を確かめる。"""
from __future__ import annotations

import re

from conftest import ROOT

TEMPLATES = ROOT / "plugins" / "ced-craft-explanation-docs" / "assets" / "templates"
FORMATS = ROOT / "plugins" / "ced-craft-explanation-docs" / "references" / "output-formats.md"
FINAL = ["README.md", "01_source.md", "02_explanation_memo.md", "11_question_and_answer.md", "12_LLM_prompts_as_guide.md"]


def placeholders(name):
    return set(re.findall(r"\{\{(\w+)\}\}", (TEMPLATES / name).read_text(encoding="utf-8")))


def test_five_templates_exist_and_start_with_nav():
    for n in FINAL:
        t = (TEMPLATES / n).read_text(encoding="utf-8")
        assert t.startswith("###### [toTopPage](./README.md)\n###### [toREADME](./README.md)\n"), n


def test_documented_placeholders_match_templates():
    doc = FORMATS.read_text(encoding="utf-8")
    sec = doc[doc.index("## 7. ひな形のプレースホルダ"):doc.index("## 8. 完了報告の形")]
    for n in FINAL:
        row = next(ln for ln in sec.splitlines() if ln.startswith(f"| `{n}`"))
        documented = set(re.findall(r"`(\w+)`", row.split("|")[2]))
        assert documented == placeholders(n), n


def test_source_template_has_body_marker_and_readme_link():
    t = (TEMPLATES / "01_source.md").read_text(encoding="utf-8")
    assert "<!-- source-body:start -->\n{{body}}" in t
    assert "[README.md](./README.md)" in t
    assert "> 要約：{{summary}}" in t


def test_readme_template_headings_are_in_required_order():
    t = (TEMPLATES / "README.md").read_text(encoding="utf-8")
    heads = re.findall(r"^## (.+)$", t, re.M)
    assert heads == ["セクション", "概要", "生成AIの総括", "本文", "解説メモ", "FAQ", "LLM 用プロンプト"]


def test_output_formats_mentions_every_check_item():
    doc = FORMATS.read_text(encoding="utf-8")
    for i in range(1, 12):
        assert f"| C-{i} |" in doc
