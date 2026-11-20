"""SKILL.md・workflows・references の取り決めのテスト（実在・整合・語の混入）。"""
from __future__ import annotations

import re

import pytest

from conftest import ROOT, run_script
import check_docs as CD

SKILL = ROOT / "plugins" / "ced-craft-explanation-docs"
MD_FILES = sorted(SKILL.rglob("*.md"))
GLOBIS_WORDS = ["GLOBIS", "グロービス", "講座ID", "学びエージェント"]


def read(rel):
    return (SKILL / rel).read_text(encoding="utf-8")


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "frontmatter が無い"
    return m.group(1)


def test_skill_md_frontmatter_name_and_description():
    fm = frontmatter(read("SKILL.md"))
    assert re.search(r"^name: ced-craft-explanation-docs$", fm, re.M)
    desc = fm[fm.index("description:"):]
    # 起動する言い回し
    for phrase in ("解説メモを作って", "この MD を解説して", "深掘りして", "講義メモにして"):
        assert phrase in desc, phrase
    # 起動しないもの（対象外）
    for other in ("url-to-md", "websearch-slide-ja", "globis-course-deepdive"):
        assert other in desc, other
    assert "対象外" in desc


def test_skill_md_is_an_entrance_not_a_manual():
    n = len(read("SKILL.md").splitlines())
    assert 60 <= n <= 140, n  # 80〜120 行が目安


def test_skill_md_has_rules_and_step0_and_failure_table():
    t = read("SKILL.md")
    for head in ("## 守ること", "## Step 0：環境と事前確認", "## モード", "## 失敗したとき", "## 関連スキル"):
        assert head in t, head
    for code in ("NO_INPUT", "EMPTY_CONTENT", "MULTI_SOURCE", "DEST_EXISTS", "UNEXPECTED"):
        assert code in t, code
    assert "`<RUN>`" in t and "`<SKILL_DIR>`" in t
    assert "質問は Step 0 の 1 回だけ" in t
    for q in ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6"):
        assert q in t


def test_referenced_files_exist():
    """SKILL.md・workflows・references が `references/…` `workflows/…` `scripts/…` `assets/…` で指すファイルが実在する。"""
    for p in MD_FILES:
        text = p.read_text(encoding="utf-8")
        for ref in re.findall(r"`((?:references|workflows|scripts|assets)/[A-Za-z0-9_./<>-]+)`", text):
            if "<" in ref:
                continue
            assert (SKILL / ref.rstrip("/")).exists(), f"{p.relative_to(SKILL)} が指す {ref} が無い"


def test_modes_table_points_to_existing_workflows():
    t = read("SKILL.md")
    mode = t[t.index("## モード"):t.index("## 失敗したとき")]
    names = re.findall(r"`workflows/([\w.-]+)`", mode)
    assert "ingest.md" in names and "analyze.md" in names
    for n in names:
        assert (SKILL / "workflows" / n).is_file(), n


def test_no_globis_terms_except_description_exclusion():
    for p in MD_FILES:
        text = p.read_text(encoding="utf-8")
        if p.name == "SKILL.md":
            body = text[len(re.match(r"^---\n.*?\n---\n", text, re.S).group(0)):]  # description は対象外の言及があってよい
            text = body
        for w in GLOBIS_WORDS:
            assert w not in text, f"{p.relative_to(SKILL)} に {w} が残っている"
    # スクリプト・ひな形にも残さない
    for p in list((SKILL / "scripts").glob("*.py")) + list((SKILL / "assets").rglob("*.md")):
        text = p.read_text(encoding="utf-8")
        for w in GLOBIS_WORDS:
            assert w not in text, f"{p.relative_to(SKILL)} に {w} が残っている"


def test_documented_options_exist_in_help():
    """文書に書いたオプションが、そのスクリプトの --help にある（--help に無いオプションを書かない）。"""
    helps = {"scaffold.py": run_script("scaffold.py", "--help").stdout,
             "check_docs.py": run_script("check_docs.py", "--help").stdout}
    for p in MD_FILES:
        for ln in p.read_text(encoding="utf-8").splitlines():
            for script, h in helps.items():
                if script in ln:
                    for opt in re.findall(r"(?<![\w-])(--[a-z][a-z-]+)", ln):
                        assert opt in h or opt in ("--python",), f"{p.relative_to(SKILL)}: {script} に {opt} は無い（{ln.strip()[:60]}）"


def test_analyze_steps_map_to_output_formats():
    analyze = read("workflows/analyze.md")
    formats = read("references/output-formats.md")
    outs = re.findall(r"`out/(\d\d_[\w-]+(?:<N>)?\.md|05_group-analysis-<N>\.md)`", analyze)
    table = formats[formats.index("### 3-1."):formats.index("## 4. out/")]
    for o in set(outs):
        if o.startswith("00_"):
            continue  # 00_run-report.md は 3 の本文で説明している
        base = o.replace("<N>", "")
        stem = re.sub(r"\.md$", "", base)
        key = stem if "group-analysis" not in stem else "05_group-analysis"
        assert key.replace("-.", "-") in table or key in table, o


def test_prompt_templates_use_headings_that_check_docs_requires():
    t = read("references/prompt-templates.md")
    step4 = t[t.index("## Step 4 テンプレート"):t.index("## Step 5 テンプレート")]
    for name in CD.THEME_H3:
        assert f"`### {name}`" in step4, name
    step1 = t[t.index("## Step 1 テンプレート"):t.index("## Step 2 テンプレート")]
    for name in CD.MEMO_H3:
        assert f"## {name}" in step1, name
    for name in ("初心者向け", "中級者向け", "上級者向け"):
        assert name in t[t.index("## Step 9 テンプレート"):]
    assert "`### 案1：<視点>`" in t[t.index("## Step 6 テンプレート"):t.index("## Step 7 テンプレート")]
    assert "**該当箇所**" in t[t.index("## Step 7 テンプレート"):t.index("## Step 8-A")]
    # 確認を取らない（globis 版からの変更）
    assert "確認を取らない" in t
    # 3 案の提案をしない
    assert "3 案の提案と選択はしない" in t


def test_step_questions_stay_in_step0():
    """質問は Step 0 の 1 回だけ。analyze.md に「ユーザーに確認」を残さない（確認を取らない旨は可）。"""
    t = read("workflows/analyze.md")
    for ln in t.splitlines():
        if "ユーザーに" in ln:
            assert any(k in ln for k in ("確認しない", "確認を取らない", "伝えて止まる", "ユーザーへ確認しない")), ln


def test_help_workflow_is_wired_and_creates_nothing():
    t = read("SKILL.md")
    desc = frontmatter(t)
    assert "使い方を教えて" in desc
    mode = t[t.index("## モード"):t.index("## 失敗したとき")]
    assert "`workflows/help.md`" in mode
    h = read("workflows/help.md")
    assert "何も作らず" in h and "スクリプトも実行せず" in h
    # 作るもの 5 本と、入力 3 種類のプロファイルに触れている
    for f in ("README.md", "01_source.md", "02_explanation_memo.md", "11_question_and_answer.md", "12_LLM_prompts_as_guide.md"):
        assert f in h, f
    for prof in ("youtube", "html", "pdf"):
        assert prof in h, prof


def test_rerun_section_matches_scaffold_status_keys():
    """analyze.md の「部分実行・再実行」が読むよう指示する JSON の項目が、scaffold.py の出力に実在する。"""
    t = read("workflows/analyze.md")
    sec = t[t.index("## 部分実行・再実行"):t.index("## 終わったら")]
    import scaffold
    keys = {"steps", "missing_steps", "groups", "input_changed"}
    for k in keys:
        assert f"`{k}`" in sec, k
    src = (SKILL / "scripts" / "scaffold.py").read_text(encoding="utf-8")
    for k in keys:
        assert f'"{k}"' in src, k
    # 波及の表が、Step 1〜8-B を扱っている
    for step in ("| 1（", "| 3（", "| 4（", "| 7（"):
        assert step in sec, step
    assert scaffold.STEP_FILES[0][0] == "1"


def test_content_types_cover_three_kinds():
    t = read("references/content-types.md")
    for k in ("学習・ビジネス", "技術・ハウツー", "考察・読み物"):
        assert k in t
    for role in ("専門教育者兼リサーチャー", "シニアエンジニア兼技術教育者", "編集者兼批評家"):
        assert role in t


def test_skill_md_has_no_script_fallback():
    """スクリプトを実行できないとき（P6）の手順が SKILL.md にあり、必要な文書を指している。"""
    t = read("SKILL.md")
    sec = t[t.index("## スクリプトを実行できないとき"):t.index("## 関連スキル")]
    assert "機械での検査は未実施" in sec and "「合格」とは書かない" in sec
    for ref in ("references/output-formats.md", "references/self-review.md", "assets/templates/", "workflows/analyze.md"):
        assert f"`{ref}`" in sec, ref
        assert (SKILL / ref.rstrip("/")).exists()
    # 完了報告の形にも、実行できなかったときの書き方がある
    assert "機械での検査は未実施" in read("workflows/review.md")
