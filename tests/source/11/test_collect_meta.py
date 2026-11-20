"""collect_sources.py の v0.0.3（V3-M2）の検査：題・日付の抽出（D21）、PDF・Office の先頭（U15）、
`01_sources/` への取得（U10）、解説済みの取得物の読み飛ばし（U19・D20）、再開の候補（D18）。

通信はしない。取得は `run_converter` を差し替えて確かめる。
"""
import datetime
import io
import json
import os
import subprocess
import sys
import zipfile

import pytest

from conftest import SCRIPTS
from pdf_fixtures import make_pdf

SCRIPT = os.path.join(SCRIPTS, "collect_sources.py")
import collect_sources as cs  # noqa: E402
import _common  # noqa: E402

TODAY = "2026-11-20"
TODAY_YMD = "261120"
BODY = "これは本文です。解説メモの入力として使う、ごく短い文章です。" * 3


def run(*args, cwd=None):
    r = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, cwd=cwd)
    return r.returncode, r.stdout.decode("utf-8"), r.stderr.decode("utf-8")


def plan(*args, cwd):
    code, out, err = run("plan", *args, "--cwd", str(cwd), "--today", TODAY, cwd=cwd)
    assert code == 0, err
    return json.loads(out)


def reason(err):
    for line in err.splitlines():
        if line.startswith("REASON="):
            return line.split("=", 1)[1]
    return None


# ---- extract_html_meta（_common）-----------------------------------------------------
def test_html_meta_prefers_article_published_time():
    html = ('<html><head><title>ページの題</title>'
            '<meta property="og:title" content="OG の題">'
            '<meta property="article:published_time" content="2025-03-04T09:00:00+09:00">'
            '</head><body><time datetime="2020-01-01">x</time></body></html>')
    m = _common.extract_html_meta(html)
    assert m["title"] == "OG の題"
    assert m["date"] == "2025-03-04"
    assert m["date_source"] == "meta:article:published_time"


def test_html_meta_json_ld_then_time_then_none():
    ld = ('<html><head><title>T</title><script type="application/ld+json">'
          '{"@type":"Article","datePublished":"2024-12-31T00:00:00Z"}</script></head></html>')
    m = _common.extract_html_meta(ld)
    assert (m["date"], m["date_source"]) == ("2024-12-31", "json-ld:datePublished")
    t = '<html><head><title>T</title></head><body><time datetime="2023-05-06">5月6日</time></body></html>'
    m = _common.extract_html_meta(t)
    assert (m["date"], m["date_source"]) == ("2023-05-06", "time:datetime")
    none = _common.extract_html_meta("<html><head><title>だけ &amp; 題</title></head><body>x</body></html>")
    assert none["date"] is None and none["title"] == "だけ & 題"


def test_html_meta_broken_json_ld_does_not_crash():
    html = '<html><head><script type="application/ld+json">{broken</script></head></html>'
    m = _common.extract_html_meta(html)
    assert m["date"] is None and m["title"] is None


# ---- 日付の整え方 ---------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("2025-01-15", "250115"),
    ("2025-01-15T10:00:00+09:00", "250115"),
    ("D:20250115103000+09'00'", "250115"),
    ("2025/1/5", "250105"),
    ("20250115", "250115"),
])
def test_resolve_date_formats(raw, expected):
    today = datetime.date(2026, 11, 20)
    assert cs.resolve_date([(raw, "x")], today) == (expected, "x")


@pytest.mark.parametrize("raw", ["1970-01-01", "2099-01-01", "ふつうの文字", "", None, "2025-13-40"])
def test_resolve_date_rejects_implausible_values_and_uses_run_date(raw):
    today = datetime.date(2026, 11, 20)
    assert cs.resolve_date([(raw, "x")], today) == (TODAY_YMD, "run_date")


def test_resolve_date_takes_first_valid_candidate():
    today = datetime.date(2026, 11, 20)
    got = cs.resolve_date([("1970-01-01", "a"), ("2024-02-03", "b"), ("2025-01-01", "c")], today)
    assert got == ("240203", "b")


# ---- plan：題と日付（ファイル）-----------------------------------------------------------
def test_markdown_frontmatter_title_and_published(tmp_path):
    f = tmp_path / "memo.md"
    f.write_text('---\ntitle: "Claude Code の手引き"\npublished: 2025-03-04\n---\n\n# 別の見出し\n\n' + BODY,
                 encoding="utf-8")
    c = plan(str(f), cwd=tmp_path)["candidates"][0]
    assert c["title"] == "Claude Code の手引き"
    assert c["date"] == "250304" and c["date_source"] == "frontmatter:published"
    assert c["items"][0]["title"] == "Claude Code の手引き"


def test_markdown_heading_title_and_run_date_without_frontmatter(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("# 見出しの題\n\n" + BODY, encoding="utf-8")
    c = plan(str(f), cwd=tmp_path)["candidates"][0]
    assert c["title"] == "見出しの題"
    assert (c["date"], c["date_source"]) == (TODAY_YMD, "run_date")


def test_text_file_without_heading_uses_file_stem_and_run_date(tmp_path):
    f = tmp_path / "meeting-notes.txt"
    f.write_text(BODY, encoding="utf-8")
    c = plan(str(f), cwd=tmp_path)["candidates"][0]
    assert c["title"] == "meeting-notes"
    assert c["items"][0]["title_source"] == "filename"
    assert (c["date"], c["date_source"]) == (TODAY_YMD, "run_date")
    assert c["items"][0]["head"].startswith("これは本文です")


def test_code_file_uses_file_name_and_run_date(tmp_path):
    f = tmp_path / "calc_stock.py"
    f.write_text("def calc():\n    return 1\n" * 10, encoding="utf-8")
    c = plan(str(f), cwd=tmp_path)["candidates"][0]
    assert c["title"] == "calc_stock"
    assert c["date_source"] == "run_date"


# ---- plan：PDF（U15）-------------------------------------------------------------------
def test_pdf_title_creation_date_and_head(tmp_path):
    f = tmp_path / "report.pdf"
    make_pdf(f, texts=["Quarterly Stock Review"],
             info={"Title": "Stock Review 2025", "CreationDate": "D:20250115103000+09'00'"})
    c = plan(str(f), cwd=tmp_path)["candidates"][0]
    it = c["items"][0]
    assert it["title"] == "Stock Review 2025" and it["title_source"] == "metadata"
    assert (c["date"], c["date_source"]) == ("250115", "pdf:CreationDate")
    assert "Quarterly Stock Review" in it["head"]


def test_pdf_without_metadata_uses_file_stem_and_run_date(tmp_path):
    f = tmp_path / "scan-report.pdf"
    make_pdf(f, texts=[None])
    c = plan(str(f), cwd=tmp_path)["candidates"][0]
    assert c["title"] == "scan-report"
    assert (c["date"], c["date_source"]) == (TODAY_YMD, "run_date")
    assert c["items"][0]["head"] == ""


def test_pdf_with_ancient_creation_date_uses_run_date(tmp_path):
    f = tmp_path / "old.pdf"
    make_pdf(f, texts=["Old"], info={"CreationDate": "D:19700101000000Z"})
    c = plan(str(f), cwd=tmp_path)["candidates"][0]
    assert (c["date"], c["date_source"]) == (TODAY_YMD, "run_date")


def test_broken_pdf_does_not_stop_plan(tmp_path):
    f = tmp_path / "broken.pdf"
    f.write_bytes(b"%PDF-1.4\nnot really")
    c = plan(str(f), cwd=tmp_path)["candidates"][0]
    assert c["title"] == "broken" and c["date_source"] == "run_date"


# ---- plan：Office（U15）---------------------------------------------------------------
def _office(path, parts):
    with zipfile.ZipFile(path, "w") as z:
        for name, body in parts.items():
            z.writestr(name, body)


CORE = ('<?xml version="1.0"?><cp:coreProperties xmlns:cp="x" xmlns:dc="y" xmlns:dcterms="z">'
        '<dc:title>在庫の見直し</dc:title>'
        '<dcterms:created xsi:type="dcterms:W3CDTF" xmlns:xsi="w">2025-02-03T01:02:03Z</dcterms:created>'
        '</cp:coreProperties>')


def test_docx_title_created_and_head(tmp_path):
    f = tmp_path / "plan.docx"
    _office(f, {"docProps/core.xml": CORE,
                "word/document.xml": '<w:document><w:body><w:p><w:r><w:t>最初の段落です</w:t></w:r></w:p>'
                                     '<w:p><w:r><w:t>二つ目</w:t></w:r></w:p></w:body></w:document>'})
    c = plan(str(f), cwd=tmp_path)["candidates"][0]
    it = c["items"][0]
    assert it["title"] == "在庫の見直し" and it["title_source"] == "metadata"
    assert (c["date"], c["date_source"]) == ("250203", "office:dcterms:created")
    assert it["head"].startswith("最初の段落です")


def test_pptx_head_uses_first_slide_and_xlsx_uses_shared_strings(tmp_path):
    p = tmp_path / "deck.pptx"
    _office(p, {"ppt/slides/slide1.xml": "<p:sld><a:t>表紙の題</a:t><a:t>副題</a:t></p:sld>",
                "ppt/slides/slide2.xml": "<p:sld><a:t>二枚目</a:t></p:sld>"})
    x = tmp_path / "book.xlsx"
    _office(x, {"xl/sharedStrings.xml": "<sst><si><t>品名</t></si><si><t>個数</t></si></sst>"})
    cp = plan(str(p), cwd=tmp_path)["candidates"][0]
    cx = plan(str(x), cwd=tmp_path)["candidates"][0]
    assert "表紙の題" in cp["items"][0]["head"] and "二枚目" not in cp["items"][0]["head"]
    assert "品名" in cx["items"][0]["head"]
    assert cp["title"] == "deck" and cp["date_source"] == "run_date"


def test_broken_office_does_not_stop_plan(tmp_path):
    f = tmp_path / "bad.docx"
    f.write_bytes(b"not a zip")
    c = plan(str(f), cwd=tmp_path)["candidates"][0]
    assert c["title"] == "bad" and c["date_source"] == "run_date"


# ---- plan：複数・URL ------------------------------------------------------------------
def test_folder_with_two_items_uses_folder_name_and_run_date(tmp_path):
    d = tmp_path / "report-pack"
    d.mkdir()
    (d / "a.md").write_text("---\npublished: 2020-01-01\n---\n\n# A\n\n" + BODY, encoding="utf-8")
    (d / "b.txt").write_text(BODY, encoding="utf-8")
    c = plan(str(d), cwd=tmp_path)["candidates"][0]
    assert c["title"] == "report-pack"
    assert (c["date"], c["date_source"]) == (TODAY_YMD, "run_date")
    assert [i["id"] for i in c["items"]] == [1, 2]
    assert c["items"][0]["date"] == "200101"


def test_url_candidate_needs_fetch_and_has_no_title(tmp_path):
    c = plan("https://example.com/post", cwd=tmp_path)["candidates"][0]
    assert c["title"] is None and c["needs_fetch"] is True
    assert (c["date"], c["date_source"]) == (TODAY_YMD, "run_date")


# ---- fetch（U10・D21）------------------------------------------------------------------
def fake_converter(monkeypatch, body, stderr="", calls=None):
    def fn(route, url, out_md):
        if calls is not None:
            calls.append((route, url))
        out_md.write_text(body, encoding="utf-8")
        return stderr
    monkeypatch.setattr(cs, "run_converter", fn)


def ns(url, cwd):
    return cs.build_parser().parse_args(["fetch", url, "--cwd", str(cwd), "--today", TODAY])


YT = "https://www.youtube.com/watch?v=abcdefghijk"


def test_fetch_youtube_uses_title_and_published_date(tmp_path, monkeypatch):
    calls = []
    fake_converter(monkeypatch, "# Claude Code Plugin Guide\n\n## 概要\n\n説明\n",
                   "[1] channel='ch' published='2025-11-18' duration='10:00'\n", calls)
    r = cs.cmd_fetch(ns(YT, tmp_path))
    assert calls == [("youtube", YT)]
    assert r["title"] == "Claude Code Plugin Guide"
    assert (r["date"], r["date_source"]) == ("251118", "youtube:upload_date")
    assert r["name"] == "251118_claude-code-plugin-guide"
    f = tmp_path / "01_sources" / "251118_claude-code-plugin-guide.md"
    assert r["path"] == str(f) and f.is_file()
    text = f.read_text(encoding="utf-8")
    assert text.startswith("---\n") and f'source_url: "{YT}"' in text
    assert "published: 2025-11-18" in text and "# Claude Code Plugin Guide" in text


def test_fetch_japanese_title_falls_back_to_source_name(tmp_path, monkeypatch):
    fake_converter(monkeypatch, "# 日本語だけの題\n\n本文\n", "published='2025-11-18'\n")
    r = cs.cmd_fetch(ns(YT, tmp_path))
    assert r["name"] == "251118_source" and r["title"] == "日本語だけの題"


def test_fetch_web_uses_meta_date_or_run_date(tmp_path, monkeypatch):
    meta = json.dumps({"title": "Building Plugins", "date": "2025-03-04",
                       "date_source": "meta:article:published_time"})
    fake_converter(monkeypatch, "本文だけ\n", f"[3] 変換中...\nMETA={meta}\n")
    r = cs.cmd_fetch(ns("https://example.com/a", tmp_path))
    assert r["title"] == "Building Plugins"
    assert (r["date"], r["date_source"]) == ("250304", "meta:article:published_time")
    assert r["name"] == "250304_building-plugins"


def test_fetch_web_without_date_uses_run_date_and_heading(tmp_path, monkeypatch):
    fake_converter(monkeypatch, "# Heading Title\n\n本文\n", "")
    r = cs.cmd_fetch(ns("https://example.com/b", tmp_path))
    assert (r["date"], r["date_source"]) == (TODAY_YMD, "run_date")
    assert r["name"] == f"{TODAY_YMD}_heading-title"


def test_fetch_same_url_again_reuses_file_without_network(tmp_path, monkeypatch):
    calls = []
    fake_converter(monkeypatch, "# Same Page\n\n本文\n", "", calls)
    first = cs.cmd_fetch(ns("https://example.com/c", tmp_path))
    second = cs.cmd_fetch(ns("https://example.com/c", tmp_path))
    assert len(calls) == 1
    assert second["reused"] is True and second["path"] == first["path"]
    assert second["title"] == "Same Page" and second["date"] == first["date"]


def test_fetch_different_url_same_name_gets_suffix(tmp_path, monkeypatch):
    fake_converter(monkeypatch, "# Same Title\n\n本文\n", "")
    a = cs.cmd_fetch(ns("https://example.com/1", tmp_path))
    b = cs.cmd_fetch(ns("https://example.com/2", tmp_path))
    assert a["name"] == f"{TODAY_YMD}_same-title" and b["name"] == f"{TODAY_YMD}_same-title-2"
    assert len(list((tmp_path / "01_sources").glob("*.md"))) == 2


def test_fetch_rejects_non_http_and_non_page_urls(tmp_path):
    code, _, err = run("fetch", "ftp://example.com/x", "--cwd", str(tmp_path))
    assert code == 3 and reason(err) == "UNSUPPORTED_SCHEME"
    code, _, err = run("fetch", "https://example.com/a.pdf", "--cwd", str(tmp_path))
    assert code == 3 and reason(err) == "FETCH_NOT_PAGE"
    assert not (tmp_path / "01_sources").exists()


def test_converter_failure_writes_nothing(tmp_path, monkeypatch):
    def boom(route, url, out_md):
        raise cs.StopReason("HTTP_ERROR", "404")
    monkeypatch.setattr(cs, "run_converter", boom)
    with pytest.raises(cs.StopReason):
        cs.cmd_fetch(ns("https://example.com/d", tmp_path))
    assert not (tmp_path / "01_sources").exists()


def test_fetched_file_is_planned_with_its_title_and_published_date(tmp_path, monkeypatch):
    fake_converter(monkeypatch, "# Claude Code Plugin Guide\n\n本文は十分に長い文章です。" * 5,
                   "published='2025-11-18'\n")
    r = cs.cmd_fetch(ns(YT, tmp_path))
    c = plan(r["path"], cwd=tmp_path)["candidates"][0]
    assert c["title"] == "Claude Code Plugin Guide"
    assert (c["date"], c["date_source"]) == ("251118", "frontmatter:published")


# ---- 解説済みの読み飛ばし（U19・D20。reviewer の H1）----------------------------------------
def mk_explained(tmp_path, folder, input_path, items, params=(6, "初めて読む人")):
    """解説済みの出力フォルダを、sources.json だけで再現する。items: [(path, sha256, status, file)]"""
    out = tmp_path / folder
    (out / ".work").mkdir(parents=True)
    data = {"schema": 1, "input": str(input_path), "input_name": "x",
            "params_sha256": cs.params_hash(*params),
            "items": [{"id": n, "slug": f"s{n}", "path": p, "kind": "markdown", "route": "copy",
                       "source_format": None, "sha256": sha, "origin": "dir", "over_estimate": False,
                       "md_path": None, "file": file, "status": st, "stage": st, "reason": None}
                      for n, (p, sha, st, file) in enumerate(items, 1)],
            "skipped": []}
    (out / ".work" / "sources.json").write_text(json.dumps(data), encoding="utf-8")
    return out


def sha(path):
    return cs.sha_file(path)


def src_dir(tmp_path, names=("a.md",)):
    d = tmp_path / "01_sources"
    d.mkdir()
    for n in names:
        (d / n).write_text(f"# {n}\n\n" + BODY, encoding="utf-8")
    return d


def test_explained_item_is_skipped_by_no_argument_plan(tmp_path):
    d = src_dir(tmp_path)
    mk_explained(tmp_path, "261118_done", d, [("a.md", sha(d / "a.md"), "done", str(d / "a.md"))])
    c = plan(cwd=tmp_path)["candidates"][0]
    assert c["items"] == [] and c["pending"] == 0 and c["all_explained"] is True
    assert {"path": "a.md", "reason": "ALREADY_EXPLAINED"} in c["skipped"]


def test_only_the_explained_one_is_skipped_and_ids_follow_the_rest(tmp_path):
    d = src_dir(tmp_path, ("a.md", "b.md"))
    mk_explained(tmp_path, "261118_done", d, [("a.md", sha(d / "a.md"), "done", str(d / "a.md"))])
    c = plan(cwd=tmp_path)["candidates"][0]
    assert [(i["id"], i["path"]) for i in c["items"]] == [(1, "b.md")]
    assert c["pending"] == 1 and c.get("all_explained") is False


def test_explained_by_a_file_input_run_is_also_skipped(tmp_path):
    """URL を取得した 1 件を、ファイルの入力として解説した（input がファイルのパス）あとの、引数なしの実行"""
    d = src_dir(tmp_path)
    f = d / "a.md"
    mk_explained(tmp_path, "261118_done", f, [("a.md", sha(f), "done", str(f))])
    assert plan(cwd=tmp_path)["candidates"][0]["pending"] == 0


@pytest.mark.parametrize("status", ["pending", "prepared", "docs_done", "failed"])
def test_not_done_items_are_not_skipped(tmp_path, status):
    d = src_dir(tmp_path)
    mk_explained(tmp_path, "261118_part", d, [("a.md", sha(d / "a.md"), status, str(d / "a.md"))])
    assert plan(cwd=tmp_path)["candidates"][0]["pending"] == 1


def test_changed_file_is_not_skipped(tmp_path):
    d = src_dir(tmp_path)
    mk_explained(tmp_path, "261118_done", d, [("a.md", "0" * 64, "done", str(d / "a.md"))])
    assert plan(cwd=tmp_path)["candidates"][0]["pending"] == 1


def test_explicit_input_is_not_skipped(tmp_path):
    d = src_dir(tmp_path)
    mk_explained(tmp_path, "261118_done", d, [("a.md", sha(d / "a.md"), "done", str(d / "a.md"))])
    assert plan(str(d), cwd=tmp_path)["candidates"][0]["pending"] == 1


def test_prepare_without_input_stops_with_all_explained_and_writes_nothing(tmp_path):
    d = src_dir(tmp_path)
    mk_explained(tmp_path, "261118_done", d, [("a.md", sha(d / "a.md"), "done", str(d / "a.md"))])
    out = tmp_path / "261120_new"
    code, _, err = run("prepare", "--cwd", str(tmp_path), "--out-dir", str(out), cwd=tmp_path)
    assert code == 3 and reason(err) == "ALL_EXPLAINED"
    assert not out.exists()


def test_prepare_without_input_skips_explained_and_records_it(tmp_path):
    d = src_dir(tmp_path, ("a.md", "b.md"))
    mk_explained(tmp_path, "261118_done", d, [("a.md", sha(d / "a.md"), "done", str(d / "a.md"))])
    out = tmp_path / "261120_new"
    code, o, err = run("prepare", "--cwd", str(tmp_path), "--out-dir", str(out), cwd=tmp_path)
    assert code == 0, err
    data = json.loads((out / ".work" / "sources.json").read_text(encoding="utf-8"))
    assert [i["path"] for i in data["items"]] == ["b.md"]
    assert {"path": "a.md", "reason": "ALREADY_EXPLAINED"} in data["skipped"]


def test_own_output_folder_is_not_counted_so_resume_keeps_done_items(tmp_path):
    d = src_dir(tmp_path)
    out = mk_explained(tmp_path, "261118_done", d, [("a.md", sha(d / "a.md"), "done", str(d / "a.md"))])
    code, o, err = run("prepare", "--cwd", str(tmp_path), "--out-dir", str(out), cwd=tmp_path)
    assert code == 0, err
    data = json.loads((out / ".work" / "sources.json").read_text(encoding="utf-8"))
    assert [(i["path"], i["status"]) for i in data["items"]] == [("a.md", "done")]


def test_zip_member_explained_is_skipped(tmp_path):
    d = tmp_path / "01_sources"
    d.mkdir()
    z = d / "pack.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.md", "# A\n\n" + BODY)
        zf.writestr("b.md", "# B\n\n" + BODY)
    first = plan(cwd=tmp_path)["candidates"][0]["items"]
    by_path = {i["path"]: i for i in first}
    a = by_path["pack.zip/a.md"]
    mk_explained(tmp_path, "261118_done", d,
                 [(a["path"], a["sha256"], "done", None)])
    # 保存済みの項目に zip_rel が入っていること（読み飛ばしの照合に使う）
    stored = json.loads((tmp_path / "261118_done" / ".work" / "sources.json").read_text(encoding="utf-8"))
    stored["items"][0].update({"origin": "zip", "zip_rel": "pack.zip"})
    (tmp_path / "261118_done" / ".work" / "sources.json").write_text(json.dumps(stored), encoding="utf-8")
    c = plan(cwd=tmp_path)["candidates"][0]
    assert [i["path"] for i in c["items"]] == ["pack.zip/b.md"]
    assert {"path": "pack.zip/a.md", "reason": "ALREADY_EXPLAINED"} in c["skipped"]


def test_prepare_records_zip_rel_for_zip_items(tmp_path):
    z = tmp_path / "pack.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.md", "# A\n\n" + BODY)
    out = tmp_path / "261120_pack"
    code, o, err = run("prepare", str(z), "--cwd", str(tmp_path), "--out-dir", str(out), cwd=tmp_path)
    assert code == 0, err
    data = json.loads((out / ".work" / "sources.json").read_text(encoding="utf-8"))
    assert data["items"][0]["zip_rel"] == "pack.zip"


# ---- 再開の候補（D18。reviewer の M2）-------------------------------------------------------
def test_plan_lists_resumable_folder_for_the_same_input(tmp_path):
    d = src_dir(tmp_path)
    mk_explained(tmp_path, "261118_part", d, [("a.md", sha(d / "a.md"), "prepared", str(d / "a.md"))])
    c = plan(cwd=tmp_path)["candidates"][0]
    assert [r["name"] for r in c["resumable"]] == ["261118_part"]


def test_plan_does_not_list_other_inputs_or_other_params(tmp_path):
    d = src_dir(tmp_path)
    other = tmp_path / "other.md"
    other.write_text("# o\n\n" + BODY, encoding="utf-8")
    mk_explained(tmp_path, "261118_other", other, [("other.md", sha(other), "prepared", str(other))])
    mk_explained(tmp_path, "261118_params", d, [("a.md", sha(d / "a.md"), "prepared", str(d / "a.md"))],
                 params=(10, "専門家"))
    c = plan(cwd=tmp_path)["candidates"][0]
    assert c["resumable"] == []


def test_plan_lists_resumable_in_the_out_parent_too(tmp_path):
    d = src_dir(tmp_path)
    parent = tmp_path / "elsewhere"
    parent.mkdir()
    mk_explained(parent, "261118_part", d, [("a.md", sha(d / "a.md"), "prepared", str(d / "a.md"))])
    c = plan("--out-dir", str(parent / "261120_x"), cwd=tmp_path)["candidates"][0]
    assert [r["name"] for r in c["resumable"]] == ["261118_part"]


# ---- reviewer の指摘への対応（V3-M2 の審査）---------------------------------------------------
def test_h2_fully_explained_folder_is_not_offered_for_a_new_item(tmp_path):
    """解説済みのフォルダを、新しい項目の候補に出さない（質問なしの実行で、別の入力が混ざるため）。"""
    d = src_dir(tmp_path, ("a.md", "b.md"))
    mk_explained(tmp_path, "261118_one", d, [("a.md", sha(d / "a.md"), "done", str(d / "a.md"))])
    c = plan(cwd=tmp_path)["candidates"][0]
    assert [i["path"] for i in c["items"]] == ["b.md"]
    assert c["resumable"] == []


def test_h2_folder_with_an_unfinished_item_is_offered(tmp_path):
    d = src_dir(tmp_path, ("a.md", "b.md"))
    mk_explained(tmp_path, "261118_two", d, [("a.md", sha(d / "a.md"), "done", str(d / "a.md")),
                                           ("b.md", sha(d / "b.md"), "prepared", str(d / "b.md"))])
    c = plan(cwd=tmp_path)["candidates"][0]
    assert [r["name"] for r in c["resumable"]] == ["261118_two"]


def test_h2_explicit_input_still_offers_a_finished_folder_for_the_same_input(tmp_path):
    """引数で入力を渡したとき（同じ入力の続き）は、done だけのフォルダも出す（D18）。"""
    d = src_dir(tmp_path)
    f = d / "a.md"
    mk_explained(tmp_path, "261118_one", f, [("a.md", sha(f), "done", str(f))])
    c = plan(str(f), cwd=tmp_path)["candidates"][0]
    assert [r["name"] for r in c["resumable"]] == ["261118_one"]


def test_m2_parent_option_finds_skips_and_resumable_in_the_out_parent(tmp_path):
    d = src_dir(tmp_path, ("a.md", "b.md"))
    parent = tmp_path / "elsewhere"
    parent.mkdir()
    mk_explained(parent, "261118_two", d, [("a.md", sha(d / "a.md"), "done", str(d / "a.md")),
                                          ("b.md", sha(d / "b.md"), "prepared", str(d / "b.md"))])
    c = plan("--parent", str(parent), cwd=tmp_path)["candidates"][0]
    assert [r["name"] for r in c["resumable"]] == ["261118_two"]
    d2 = src_dir(tmp_path / "x", ("c.md",)) if (tmp_path / "x").mkdir() is None else None
    mk_explained(parent, "261118_done", d2, [("c.md", sha(d2 / "c.md"), "done", str(d2 / "c.md"))])
    c2 = plan("--parent", str(parent), "--source-dir", str(d2), cwd=tmp_path)["candidates"][0]
    assert c2["pending"] == 0 and c2["all_explained"] is True


def test_l9_fetched_body_ends_with_a_newline(tmp_path, monkeypatch):
    fake_converter(monkeypatch, "# T\n\n本文だけ", "")
    r = cs.cmd_fetch(ns("https://example.com/nl", tmp_path))
    assert open(r["path"], encoding="utf-8").read().endswith("本文だけ\n")


def test_l10_code_comment_is_not_a_title(tmp_path):
    f = tmp_path / "q.py"
    f.write_text("# comment line that is not a title\n" + "x = 1\n" * 20, encoding="utf-8")
    c = plan(str(f), cwd=tmp_path)["candidates"][0]
    assert c["title"] == "q" and c["items"][0]["title_source"] == "filename"


# ---- PDF の解析に、時間とメモリの上限（M3・M4）-------------------------------------------------
def test_m3_compression_bomb_is_bounded(tmp_path):
    import resource  # noqa: F401  (unix のみ。無ければ、このテストは飛ばす)
    import zlib
    bomb = zlib.compress(b"\0" * (300 * 1024 * 1024), 9)
    pdf = (b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\nstream\n" + bomb + b"\nendstream\n"
           b"trailer<</Root 1 0 R>>\n%%EOF\n")
    f = tmp_path / "bomb.pdf"
    f.write_bytes(pdf)
    # 最大常駐量（ru_maxrss。macOS はバイト、Linux は KB）で測る。上限なしで展開すると 300 MB を超える
    code = ("import resource,sys;"
            f"sys.path.insert(0,{SCRIPTS!r});import collect_sources as cs,datetime;"
            f"m=cs.meta_pdf(open({str(f)!r},'rb').read(),'bomb',datetime.date(2026,11,20));"
            "unit=1 if sys.platform=='darwin' else 1024;"
            "print(m['title'], resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*unit//(1024*1024))")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=60)
    assert r.returncode == 0, r.stderr.decode()[-300:]
    title, mb = r.stdout.decode().split()
    assert title == "bomb"
    assert int(mb) < 200, f"最大常駐量が {mb} MB"


def test_m4_many_unterminated_streams_finish_quickly(tmp_path):
    f = tmp_path / "broken.pdf"
    f.write_bytes(b"%PDF-1.4\n" + b"stream\nxxxxxxxxxxxxxxxxxxxxxxxx\n" * 60000)
    r = subprocess.run([sys.executable, SCRIPT, "plan", str(f), "--cwd", str(tmp_path), "--today", TODAY],
                       capture_output=True, timeout=30)
    assert r.returncode == 0, r.stderr.decode()[-300:]
    assert json.loads(r.stdout.decode("utf-8"))["candidates"][0]["title"] == "broken"
