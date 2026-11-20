"""scaffold.py のテスト：3 種の入力から作業フォルダ・01_source.md・manifest・README の骨格ができる。"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys

import pytest

from conftest import GOLDEN_VIDEO, INPUTS, ROOT, run_script
import _common as C
from check_docs import run_checks

SIBLING = ROOT / "plugins" / "ced-url-to-md" / "scripts" / "add_frontmatter.py"

PROFILES = {
    "video.md": "video", "video-nochapter.md": "video", "article.md": "article",
    "document.md": "document", "document-direct.md": "document", "plain.md": "article",
}


@pytest.fixture
def work(tmp_path):
    """入力の見本を tmp にコピーして返す関数。"""
    def make(name):
        p = tmp_path / name
        shutil.copy(INPUTS / name, p)
        return p
    return make


def scaffold(path, *args):
    p = run_script("scaffold.py", path, *args)
    return p, (json.loads(p.stdout) if p.stdout.strip() else None)


def body_of(folder):
    return C.split_source((folder / "01_source.md").read_text(encoding="utf-8"))[1]


@pytest.mark.parametrize("name,profile", PROFILES.items())
def test_creates_folder_for_each_fixture(work, name, profile):
    src = work(name)
    before = src.read_bytes()
    p, r = scaffold(src)
    assert p.returncode == 0, p.stderr
    dest = src.parent / (src.stem + "_explained")
    assert r["dest"] == str(dest) and r["profile"] == profile and r["mode"] == "created"
    for f in ("README.md", "01_source.md", "out/00_manifest.json", "out/00_run-report.md"):
        assert (dest / f).is_file(), f
    # 入力は変わらない（ハッシュで確認）
    assert src.read_bytes() == before
    assert hashlib.sha256(before).hexdigest() == json.loads((dest / "out/00_manifest.json").read_text())["input"]["sha256"]


@pytest.mark.parametrize("name", PROFILES)
def test_source_body_is_exact_copy_of_input_body(work, name):
    src = work(name)
    scaffold(src)
    dest = src.parent / (src.stem + "_explained")
    _, want, _ = C.parse_frontmatter(src.read_text(encoding="utf-8"))
    assert body_of(dest) == C.normalize_body(want)  # 一字も変えない（末尾の改行は 1 つ）
    m = json.loads((dest / "out/00_manifest.json").read_text(encoding="utf-8"))
    assert m["body_sha256"] == C.sha256_text(C.normalize_body(want))
    # C-9（入力の保全）が通る
    r = run_checks(str(dest), only={"C-9"})
    assert r["items"][0]["status"] == "PASS", r


def test_scaffold_output_matches_golden_for_video(work):
    """手作りの合格見本と、本文・ハッシュ・題名の箇条書きが同じ（見本の冒頭の決まりと scaffold が一致）。"""
    src = work("video.md")
    scaffold(src)
    dest = src.parent / "video_explained"
    got = (dest / "01_source.md").read_text(encoding="utf-8")
    want = (GOLDEN_VIDEO / "01_source.md").read_text(encoding="utf-8")
    assert C.split_source(got)[1] == C.split_source(want)[1]
    assert got.split("> 要約：")[0] == want.split("> 要約：")[0]  # ナビ・題名・箇条書き・入口リンクが同じ
    gm = json.loads((dest / "out/00_manifest.json").read_text(encoding="utf-8"))
    wm = json.loads((GOLDEN_VIDEO / "out/00_manifest.json").read_text(encoding="utf-8"))
    assert gm["body_sha256"] == wm["body_sha256"] and gm["frontmatter"] == wm["frontmatter"]


def test_skeleton_leaves_placeholders_for_llm(work):
    src = work("article.md")
    scaffold(src)
    dest = src.parent / "article_explained"
    s = (dest / "01_source.md").read_text(encoding="utf-8")
    head = C.split_source(s)[0]
    assert "{{summary}}" in head and "{{toc_block}}" in head
    r = (dest / "README.md").read_text(encoding="utf-8")
    for k in ("{{sections}}", "{{overview}}", "{{summary_block}}", "{{content_type}}"):
        assert k in r, k
    assert "- `profile`: article" in r
    assert "{{title}}" not in r and "{{meta_bullets}}" not in r and "{{body}}" not in s
    # 骨格のままでは C-4 が落ちる（LLM が埋めるまで終われない）
    assert run_checks(str(dest), only={"C-4"})["items"][0]["status"] == "FAIL"
    # 足りない 3 本は C-1 が報告する
    f = run_checks(str(dest), only={"C-1"})["items"][0]["findings"]
    assert {x["file"] for x in f} == {"02_explanation_memo.md", "11_question_and_answer.md", "12_LLM_prompts_as_guide.md"}


def test_video_chapters_become_toc_lines(work):
    src = work("video.md")
    _, r = scaffold(src)
    s = r["sections"]
    assert s["source"] == "chapters" and len(s["chapters"]) == 6
    assert s["toc_for_source"][0] == "- 1 : はじめに ｜ 00:00〜00:40"
    assert s["toc_for_source"][-1] == "- 6 : まとめ ｜ 04:50〜05:20"  # 最後の終わりは動画の長さ
    assert s["toc_for_source"] == s["toc_for_readme"]
    # 見本の目次と同じ
    golden = C.split_source((GOLDEN_VIDEO / "01_source.md").read_text(encoding="utf-8"))[0]
    for ln in s["toc_for_source"]:
        assert ln in golden


def test_video_without_chapters_has_no_candidates(work):
    """チャプターが無い動画：概要・Transcript の見出しはセクションではない。スキルが区切る。"""
    src = work("video-nochapter.md")
    _, r = scaffold(src)
    assert r["profile"] == "video"
    assert r["sections"]["chapters"] == []
    assert r["sections"]["source"] == "none"
    assert r["sections"]["toc_for_source"] == [] and r["sections"]["toc_for_readme"] == []
    assert "スキルが" in r["sections"]["note"]


def test_article_headings_become_linked_toc_with_valid_anchors(work):
    src = work("article.md")
    _, r = scaffold(src)
    dest = src.parent / "article_explained"
    s = r["sections"]
    assert s["source"] == "headings"
    titles = [h["title"] for h in s["headings"] if h["level"] == 2]
    assert titles[0] == "なぜ週次レビューは長引くのか" and len(titles) == 5
    assert s["toc_for_source"][0].startswith("- 1 : [なぜ週次レビューは長引くのか](#")
    assert s["toc_for_readme"][0].startswith("- 1 : [なぜ週次レビューは長引くのか](./01_source.md#")
    anchors = C.heading_anchors((dest / "01_source.md").read_text(encoding="utf-8"))
    for h in s["headings"]:
        assert h["anchor"] in anchors
    # コードブロックの中の `## 今週やったこと` は見出しに数えない
    assert "今週やったこと" not in titles


def test_document_direct_slides_are_headings(work):
    src = work("document-direct.md")
    _, r = scaffold(src)
    assert r["profile"] == "document"
    assert r["frontmatter"]["conversion"] == "direct"
    assert r["sections"]["source"] == "headings"


def test_plain_without_frontmatter_continues_with_warning(work):
    src = work("plain.md")
    p, r = scaffold(src)
    assert p.returncode == 0
    assert "[warn] frontmatter なし" in p.stderr
    assert r["frontmatter"] == {} and r["frontmatter_warnings"][0] == "frontmatter なし"
    assert r["title"] == "打ち合わせメモ（在庫の棚卸しの進め方）"  # 本文の題名から
    assert r["profile"] == "article" and "frontmatter なし" in r["profile_reason"]
    assert r["sections"]["source"] == "none" and r["sections"]["toc_for_source"] == []  # 見出しが無い → 目次を省く
    dest = src.parent / "plain_explained"
    report = (dest / "out/00_run-report.md").read_text(encoding="utf-8")
    assert "frontmatter: なし" in report
    readme = (dest / "README.md").read_text(encoding="utf-8")
    assert "`source_format`" not in readme  # 分かる項目だけ書く


def test_profile_guessed_from_body_without_frontmatter(tmp_path):
    video = tmp_path / "v.md"
    video.write_text("# 字幕\n\n" + "\n\n".join(f"**[00:{i:02d}]** これは字幕の行です" for i in range(0, 50, 10)) + "\n", encoding="utf-8")
    _, r = scaffold(video)
    assert r["profile"] == "video"
    doc = tmp_path / "d.md"
    doc.write_text("<!-- Slide number: 1 -->\n# A\n本文本文本文本文本文\n\n<!-- Slide number: 2 -->\n# B\n本文本文本文本文\n", encoding="utf-8")
    _, r = scaffold(doc)
    assert r["profile"] == "document"


def test_local_path_source_url_is_not_shown_as_url(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("---\ntitle: 題\nsource_url: /Users/x/plan.pptx\nsource_format: pptx\nconversion: direct\n---\n"
                 "# 題\n\n本文本文本文本文本文本文本文本文本文本文本文本文本文。\n", encoding="utf-8")
    _, r = scaffold(p)
    assert r["url"] is None
    assert "`url`" not in (tmp_path / "d_explained" / "README.md").read_text(encoding="utf-8")


def test_dest_exists_stops_and_writes_nothing(work):
    src = work("video.md")
    dest = src.parent / "video_explained"
    dest.mkdir()
    (dest / "keep.txt").write_text("そのまま", encoding="utf-8")
    p = run_script("scaffold.py", src)
    assert p.returncode == 1
    assert p.stderr.strip().splitlines()[-1] == "REASON=DEST_EXISTS"
    assert [x.name for x in dest.iterdir()] == ["keep.txt"]
    assert (dest / "keep.txt").read_text(encoding="utf-8") == "そのまま"


def test_explicit_dest(work, tmp_path):
    src = work("article.md")
    d = tmp_path / "elsewhere" / "name"
    _, r = scaffold(src, "--dest", d)
    assert r["dest"] == str(d) and (d / "01_source.md").is_file()


def test_dry_run_writes_nothing(work):
    src = work("video.md")
    p, r = scaffold(src, "--dry-run")
    assert p.returncode == 0 and r["dry_run"] is True and r["files"]
    assert not (src.parent / "video_explained").exists()


def test_multi_source(work):
    a, b = work("video.md"), work("article.md")
    p = run_script("scaffold.py", a, b)
    assert p.returncode == 1 and p.stderr.strip().splitlines()[-1] == "REASON=MULTI_SOURCE"
    assert not (a.parent / "video_explained").exists()


def test_url_is_not_fetched():
    p = run_script("scaffold.py", "https://example.com/a")
    assert p.returncode == 1
    last = p.stderr.strip().splitlines()
    assert last[-1] == "REASON=NO_INPUT" and "url-to-md" in last[-2]


def test_missing_file_and_empty_input(tmp_path):
    p = run_script("scaffold.py", tmp_path / "nope.md")
    assert p.returncode == 1 and p.stderr.strip().splitlines()[-1] == "REASON=NO_INPUT"
    e = tmp_path / "e.md"
    e.write_text("", encoding="utf-8")
    p = run_script("scaffold.py", e)
    assert p.returncode == 1 and p.stderr.strip().splitlines()[-1] == "REASON=EMPTY_CONTENT"
    s = tmp_path / "s.md"
    s.write_text("---\ntitle: 題\nsource_url: u\nsource_format: html\n---\n短い\n", encoding="utf-8")
    p = run_script("scaffold.py", s)
    assert p.stderr.strip().splitlines()[-1] == "REASON=EMPTY_CONTENT"
    assert not (tmp_path / "s_explained").exists()


def test_crlf_input_gives_same_body_hash(tmp_path):
    lf = INPUTS / "article.md"
    crlf = tmp_path / "a.md"
    crlf.write_bytes(lf.read_bytes().replace(b"\n", b"\r\n"))
    _, r1 = scaffold(crlf)
    ref = tmp_path / "b.md"
    shutil.copy(lf, ref)
    _, r2 = scaffold(ref)
    assert r1["body_sha256"] == r2["body_sha256"]
    assert b"\r" not in (tmp_path / "a_explained" / "01_source.md").read_bytes()


def test_existing_folder_is_reported_not_rewritten(tmp_path):
    d = tmp_path / "w"
    shutil.copytree(GOLDEN_VIDEO, d)
    before = {p: p.read_bytes() for p in d.rglob("*") if p.is_file()}
    p, r = scaffold(d)
    assert p.returncode == 0 and r["mode"] == "existing_folder"
    assert r["source_has_body_marker"] and r["source_has_summary"] and r["source_has_toc"]
    assert r["files"]["12_LLM_prompts_as_guide.md"] is True
    assert before == {p: p.read_bytes() for p in d.rglob("*") if p.is_file()}


def test_folder_without_readme_is_no_input(tmp_path):
    (tmp_path / "x").mkdir()
    p = run_script("scaffold.py", tmp_path / "x")
    assert p.returncode == 1 and p.stderr.strip().splitlines()[-1] == "REASON=NO_INPUT"


def test_help_has_contract():
    p = run_script("scaffold.py", "--help")
    assert p.returncode == 0
    for w in ("--dest", "--dry-run", "DEST_EXISTS", "MULTI_SOURCE", "EMPTY_CONTENT", "NO_INPUT", "終了コード"):
        assert w in p.stdout


@pytest.mark.skipif(not SIBLING.is_file(), reason="11_ のリポジトリが隣に無い")
@pytest.mark.parametrize("fmt,extra,profile", [
    ("html", [], "article"), ("pdf", ["--conversion", "pdf"], "document"),
    ("pptx", ["--conversion", "direct"], "document"), ("docx", [], "document"), ("xlsx", [], "document"),
    ("youtube", ["--channel", "c", "--published", "2026-01-01", "--duration", "10:00"], "video"),
])
def test_scaffold_reads_real_add_frontmatter_output(tmp_path, fmt, extra, profile):
    """11_ の add_frontmatter.py の実出力を、scaffold が読めて、プロファイルを決められる。"""
    body = tmp_path / "b.md"
    body.write_text("# 実出力の確認\n\n" + "本文の段落です。" * 10 + "\n", encoding="utf-8")
    out = tmp_path / "in.md"
    subprocess.run([sys.executable, str(SIBLING), str(body), "--url", "https://example.com/x", "--format", fmt, *extra, "-o", str(out)],
                   check=True, capture_output=True)
    p, r = scaffold(out)
    assert p.returncode == 0, p.stderr
    assert r["profile"] == profile and r["frontmatter_warnings"] == []
    assert r["title"] == "実出力の確認" and r["url"] == "https://example.com/x"
