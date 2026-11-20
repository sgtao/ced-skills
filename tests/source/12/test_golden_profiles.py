"""article・document の合格見本（P5）：通し実行（新しいサブエージェントがスキルとして実行）で出来た作業フォルダ。

見本の `out/` と最終ファイルは LLM が書いたもの。ここでは「形の検査に合格する」「`out/` から転記し直すと同じ」
「入力と本文が同じ」「壊すと該当の項目だけ落ちる」を確かめる（文面の良し悪しは確かめない）。
入力は自作（tests/fixtures/inputs/）。
"""
from __future__ import annotations

import json
import shutil

import pytest

from conftest import FIXTURES, INPUTS, edit, run_script
from check_docs import run_checks

GOLDEN = FIXTURES / "golden"
KINDS = {"article": "article", "document": "document", "document-direct": "document"}


@pytest.fixture(params=sorted(KINDS))
def kind(request):
    return request.param


@pytest.fixture
def work(kind, tmp_path):
    dst = tmp_path / kind
    shutil.copytree(GOLDEN / kind, dst)
    return dst


def failed(folder, only=None):
    return [i["id"] for i in run_checks(str(folder), only)["items"] if i["status"] == "FAIL"]


def test_golden_passes_all_checks(work):
    out = run_checks(str(work))
    assert out["passed"], [i for i in out["items"] if i["status"] == "FAIL"]


def test_assemble_reproduces_final_files(work):
    """`out/` から転記し直しても、最終ファイルは 1 バイトも変わらない（転記は機械で、冪等）。"""
    before = {p.name: p.read_bytes() for p in work.glob("*.md")}
    p = run_script("assemble.py", work)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["written"] == []
    assert before == {p.name: p.read_bytes() for p in work.glob("*.md")}


def test_source_body_equals_current_input(kind, work, tmp_path):
    """見本の本文のハッシュは、いまの入力の見本から scaffold で作ったものと同じ（本文は変えない）。"""
    src = tmp_path / f"{kind}.md"
    shutil.copy(INPUTS / f"{kind}.md", src)
    p = run_script("scaffold.py", src)
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout)
    m = json.loads((work / "out/00_manifest.json").read_text(encoding="utf-8"))
    assert r["body_sha256"] == m["body_sha256"]
    assert r["profile"] == m["profile"] == KINDS[kind]


# ---- プロファイルごとの壊し方 ------------------------------------------------------------
def test_article_quote_is_checked_against_body(tmp_path):
    w = tmp_path / "a"
    shutil.copytree(GOLDEN / "article", w)
    edit(w, "11_question_and_answer.md", "肝心の判断事項に着くのが遅れます。", "肝心の判断事項に着くのが早くなります。")
    assert failed(w) == ["C-8"]


def test_article_code_block_in_out_does_not_break_headings(tmp_path):
    """記事のコードを out/05 に引用していて、その中に `## …` の行がある。見出しとして扱われず、転記も検査も通る。"""
    w = tmp_path / "a"
    shutil.copytree(GOLDEN / "article", w)
    o5 = (w / "out/05_group-analysis-2.md").read_text(encoding="utf-8")
    assert "```markdown" in o5 and "\n## 今週やったこと" in o5  # 見本の前提
    assert run_checks(str(w))["passed"]


def test_document_figure_quote_is_checked(tmp_path):
    w = tmp_path / "d"
    shutil.copytree(GOLDEN / "document", w)
    edit(w, "11_question_and_answer.md", "「4月 100」「8月 135」", "「4月 100」「8月 140」")
    assert failed(w) == ["C-8"]


def test_document_direct_supplement_section_quote_is_checked(tmp_path):
    w = tmp_path / "p"
    shutil.copytree(GOLDEN / "document-direct", w)
    edit(w, "11_question_and_answer.md", "スライド 4: 図形（矢印・枠・図解など） 3 個」", "スライド 4: 図形（矢印・枠・図解など） 4 個」")
    assert failed(w) == ["C-8"]


def test_body_change_is_caught_in_all_kinds(work):
    t = (work / "01_source.md").read_text(encoding="utf-8")
    marker = "<!-- source-body:start -->"
    head, body = t.split(marker, 1)
    (work / "01_source.md").write_text(head + marker + body.replace("。", "．", 1), encoding="utf-8")
    assert "C-9" in failed(work)


# ---- scaffold が返すセクション（プロファイルの文書に書いたことの裏付け）------------------------
def sections(kind, tmp_path):
    src = tmp_path / f"{kind}.md"
    shutil.copy(INPUTS / f"{kind}.md", src)
    p = run_script("scaffold.py", src, "--dry-run")
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)["sections"]


def test_article_title_h1_is_not_a_section(tmp_path):
    s = sections("article", tmp_path)
    assert [h["level"] for h in s["headings"]] == [2] * 5
    assert not any("週次レビューを30分で" in l for l in s["toc_for_source"])


def test_document_title_h1_is_not_a_section_and_number_stays(tmp_path):
    s = sections("document", tmp_path)
    assert s["toc_for_source"][0].startswith("- 1 : [1. 目的と範囲]")  # 見出しの番号が名前に残る
    assert not any("店舗在庫の見直し報告" in l for l in s["toc_for_source"])


def test_pptx_cover_slide_is_not_a_section(tmp_path):
    s = sections("document-direct", tmp_path)
    toc = s["toc_for_source"]
    assert len(toc) == 4 and toc[0].startswith("- 1 : [回転率とは]")  # 表紙（スライド 1）は入らない
    assert not any("在庫見直しの進め方" in l for l in toc)
