"""取り込み（workflows/ingest.md）の手順どおりに骨格を埋めると、C-5・C-9・C-10・C-11 が通ること。
あわせて、取り込みの文書（input-contract.md・profiles・ingest.md）が実在するファイルと一致すること。"""
from __future__ import annotations

import json
import re
import shutil

import pytest

from conftest import INPUTS, ROOT, run_script
from check_docs import run_checks
import scaffold as S

SKILL = ROOT / "plugins" / "ced-craft-explanation-docs"
INGEST_CHECKS = {"C-5", "C-9", "C-10", "C-11"}


def ingest(tmp_path, name, split_lines=None, overview="本文の概要です。" * 10):
    """ingest.md の手順 1〜5 を行う（LLM がやることを、決まった文面で代行）。"""
    src = tmp_path / name
    shutil.copy(INPUTS / name, src)
    p = run_script("scaffold.py", src)
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout)
    dest = tmp_path / r["dest"].split("/")[-1]
    sec = r["sections"]
    toc_src = split_lines if split_lines is not None else sec["toc_for_source"]
    toc_rd = split_lines if split_lines is not None else sec["toc_for_readme"]
    s = (dest / "01_source.md").read_text(encoding="utf-8")
    s = s.replace("{{summary}}", "要約です。")
    block = ("-----\n[toTop](#totoppage)\n## セクション目次\n" + "\n".join(toc_src) + "\n\n") if toc_src else ""
    s = s.replace("{{toc_block}}", block)
    (dest / "01_source.md").write_text(s, encoding="utf-8")
    rd = (dest / "README.md").read_text(encoding="utf-8")
    sections = ("入力の見出しによる区切りです。\n\n" + "\n".join(toc_rd)) if toc_rd else "分割なし"
    rd = rd.replace("{{sections}}", sections).replace("{{overview}}", overview).replace("{{content_type}}", "学習・ビジネス")
    (dest / "README.md").write_text(rd, encoding="utf-8")
    return dest, r


@pytest.mark.parametrize("name", ["video.md", "article.md", "document.md", "document-direct.md", "plain.md"])
def test_ingest_steps_make_ingest_checks_pass(tmp_path, name):
    dest, r = ingest(tmp_path, name)
    res = run_checks(str(dest), only=INGEST_CHECKS)
    assert res["passed"], res
    # 取り込みの段階で、まだ残っているのは総括の場所だけ（C-4 は落ちるのが正しい）
    left = re.findall(r"\{\{(\w+)\}\}", (dest / "README.md").read_text(encoding="utf-8"))
    assert left == ["summary_block"]


def test_ingest_video_without_chapters_skill_splits(tmp_path):
    lines = ["- 1 : 導入 ｜ スキルが区切った・00:00〜01:10・「はいみなさんこんにちは今日は」",
             "- 2 : 計算 ｜ スキルが区切った・01:10〜04:10・「眠っている在庫には三つの困り」",
             "- 3 : 習慣とまとめ ｜ スキルが区切った・04:10〜05:20・「今日からできる習慣を三つ紹」"]
    dest, _ = ingest(tmp_path, "video-nochapter.md", split_lines=lines)
    assert run_checks(str(dest), only=INGEST_CHECKS)["passed"]
    body = (dest / "01_source.md").read_text(encoding="utf-8").split("<!-- source-body:start -->")[1]
    assert "スキルが区切った" not in body  # 本文には何も挿入していない


def test_article_readme_links_into_source_headings_resolve(tmp_path):
    dest, r = ingest(tmp_path, "article.md")
    readme = (dest / "README.md").read_text(encoding="utf-8")
    assert "](./01_source.md#なぜ週次レビューは長引くのか)" in readme
    assert run_checks(str(dest), only={"C-5"})["passed"]
    # 見出しを壊すとリンク切れが見つかる（アンカーを本当に確かめている）
    p = dest / "01_source.md"
    p.write_text(p.read_text(encoding="utf-8").replace("## なぜ週次レビューは長引くのか", "## 別の見出し"), encoding="utf-8")
    assert not run_checks(str(dest), only={"C-5"})["passed"]


def test_ingest_changing_the_body_fails_c9(tmp_path):
    dest, _ = ingest(tmp_path, "article.md")
    p = dest / "01_source.md"
    p.write_text(p.read_text(encoding="utf-8").replace("決まり3：記録の担当を固定する", "決まり3：記録の担当を決める"), encoding="utf-8")
    res = run_checks(str(dest), only={"C-9"})
    assert not res["passed"]


# ---- 文書と実物の整合 --------------------------------------------------------------------
def test_profile_table_matches_code():
    doc = (SKILL / "references" / "input-contract.md").read_text(encoding="utf-8")
    for fmt, prof in S.FORMAT_TO_PROFILE.items():
        assert re.search(rf"`{fmt}`.*\| `{prof}` \|", doc), (fmt, prof)
    for prof in ("video", "article", "document"):
        assert (SKILL / "references" / "profiles" / f"{prof}.md").is_file()


def test_referenced_files_exist():
    for doc in ("references/input-contract.md", "workflows/ingest.md", *[f"references/profiles/{p}.md" for p in ("video", "article", "document")]):
        text = (SKILL / doc).read_text(encoding="utf-8")
        for ref in re.findall(r"`((?:references|workflows|scripts|assets)/[\w./<>名前-]+)`", text):
            if "<" in ref:
                continue
            assert (SKILL / ref.rstrip("/")).exists(), f"{doc} が指す {ref} が無い"


def test_ingest_options_exist_in_help():
    help_text = run_script("scaffold.py", "--help").stdout
    ingest_text = (SKILL / "workflows" / "ingest.md").read_text(encoding="utf-8")
    for opt in set(re.findall(r"(?<![\w-])(--[a-z][a-z-]+)", ingest_text)):
        if opt in ("--help", "--only"):
            continue  # --only は check_docs.py のオプション
        assert opt in help_text, f"ingest.md の {opt} が scaffold.py --help に無い"
    check_help = run_script("check_docs.py", "--help").stdout
    assert "--only" in check_help


def test_docs_do_not_mention_globis_terms():
    for p in SKILL.rglob("*.md"):
        t = p.read_text(encoding="utf-8")
        for w in ("GLOBIS", "講座ID", "学びエージェント"):
            if w in t and p.name != "SKILL.md":
                # description の「対象外」の言及だけは SKILL.md（P3）で許す。それ以外には残さない
                raise AssertionError(f"{p.relative_to(SKILL)} に {w} がある")
