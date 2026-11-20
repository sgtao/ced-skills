"""_common.py のテスト（frontmatter の読み取り・文字数・ハッシュ・見出し・理由コード）。"""
from __future__ import annotations

import subprocess
import sys

import pytest

from conftest import INPUTS, ROOT, run_script
import _common as C

SIBLING = ROOT / "plugins" / "ced-url-to-md" / "scripts" / "add_frontmatter.py"


# ---- frontmatter ----------------------------------------------------------------
@pytest.mark.parametrize("name,fmt,conv", [
    ("video.md", "youtube", None), ("video-nochapter.md", "youtube", None),
    ("article.md", "html", None), ("document.md", "pdf", "pdf"), ("document-direct.md", "pptx", "direct"),
])
def test_parse_fixture_frontmatter(name, fmt, conv):
    fm, body, warns = C.parse_frontmatter((INPUTS / name).read_text(encoding="utf-8"))
    assert warns == []
    assert fm["source_format"] == fmt
    assert fm.get("conversion") == conv
    assert fm["title"] and fm["source_url"].startswith("https://")
    assert fm["has_figures"] in ("true", "false")
    assert body.startswith(("# ", "<!--")), body[:20]


def test_parse_video_extra_keys_and_quotes():
    fm, body, _ = C.parse_frontmatter((INPUTS / "video.md").read_text(encoding="utf-8"))
    assert fm["channel"] == "サンプル講座チャンネル"
    assert fm["published"] == "2026-10-01"
    assert fm["duration"] == "05:20"  # "05:20" と引用符つきで書かれている
    assert fm["source_url"] == "https://www.youtube.com/watch?v=sample-0001"  # 引用符を外す


def test_plain_without_frontmatter_does_not_stop():
    text = (INPUTS / "plain.md").read_text(encoding="utf-8")
    fm, body, warns = C.parse_frontmatter(text)
    assert fm == {} and body == text
    assert warns == ["frontmatter なし"]


def test_missing_keys_warn_but_do_not_fail():
    fm, body, warns = C.parse_frontmatter("---\ntitle: 題\n---\n本文\n")
    assert fm == {"title": "題"} and body == "本文\n"
    assert "frontmatter の項目が無い: source_url" in warns
    assert "frontmatter の項目が無い: source_format" in warns


def test_unclosed_frontmatter_is_treated_as_none():
    fm, body, warns = C.parse_frontmatter("---\ntitle: 題\n本文\n")
    assert fm == {} and warns and "frontmatter なし" in warns[0]


def test_unknown_keys_are_ignored():
    fm, _, _ = C.parse_frontmatter("---\ntitle: 題\nsource_url: u\nsource_format: html\nfuture_key: x\n---\nB\n")
    assert "future_key" not in fm


def test_escaped_quote_in_value():
    fm, _, _ = C.parse_frontmatter('---\ntitle: "a \\"b\\": c"\nsource_url: u\nsource_format: html\n---\nB\n')
    assert fm["title"] == 'a "b": c'


def test_crlf_input_is_normalized():
    fm, body, _ = C.parse_frontmatter("---\r\ntitle: 題\r\nsource_url: u\r\nsource_format: html\r\n---\r\n本文\r\n")
    assert fm["title"] == "題" and body == "本文\n"


@pytest.mark.skipif(not SIBLING.is_file(), reason="11_ のリポジトリが隣に無い")
@pytest.mark.parametrize("fmt,extra", [
    ("html", []), ("pdf", ["--conversion", "pdf"]), ("pptx", ["--conversion", "direct"]),
    ("youtube", ["--channel", "ch", "--published", "2026-01-02", "--duration", "12:34"]),
])
def test_reads_real_output_of_add_frontmatter(tmp_path, fmt, extra):
    """R-3: 11_ の add_frontmatter.py の実出力を読ませる（項目名が変わったら、ここで気づく）。"""
    body = tmp_path / "b.md"
    body.write_text("# 題名: コロンあり\n\n最初の段落です。\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(SIBLING), str(body), "--url", "https://example.com/a?x=1",
                        "--format", fmt, "--retrieved-at", "2026-11-13T09:00:00+09:00", *extra],
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    fm, b, warns = C.parse_frontmatter(p.stdout)
    assert warns == []
    assert fm["title"] == "題名: コロンあり"
    assert fm["source_url"] == "https://example.com/a?x=1"
    assert fm["source_format"] == fmt
    assert fm["retrieved_at"] == "2026-11-13T09:00:00+09:00"
    assert fm["summary"] == "最初の段落です。"
    assert b == "# 題名: コロンあり\n\n最初の段落です。\n"
    if fmt == "youtube":
        assert (fm["channel"], fm["published"], fm["duration"]) == ("ch", "2026-01-02", "12:34")


# ---- 本文の正規化・ハッシュ -----------------------------------------------------------
def test_normalize_body():
    assert C.normalize_body("a\r\nb\r\n\r\n\r\n") == "a\nb\n"
    assert C.normalize_body("a\nb") == "a\nb\n"
    assert C.normalize_body("\n\n  \n") == ""
    assert C.normalize_body("﻿a\n") == "a\n"
    assert C.normalize_body("a\n\n\nb\n") == "a\n\n\nb\n"  # 途中は変えない


def test_sha256_text_is_stable():
    assert C.sha256_text("あ\n") == C.sha256_text("あ\n")
    assert len(C.sha256_text("x")) == 64


# ---- 文字数 ---------------------------------------------------------------------------
def test_char_count_markdown():
    assert C.char_count("あいう\nえお") == 5
    assert C.char_count("## 見出し\n本文") == 5  # 行頭の # は数えない
    assert C.char_count("- 項目1\n- 項目2") == 6
    assert C.char_count("**太字**と`コード`") == 6  # 太字2＋と1＋コード3
    assert C.char_count("[リンク](http://x.example/a)") == 3
    assert C.char_count("あ　い　う") == 3  # 全角空白も数えない
    assert C.char_count("| a | b |") == 2


def test_char_count_is_codepoints_not_bytes():
    assert C.char_count("日本語") == 3
    assert C.char_count("a😀b") == 3


def test_char_count_code_mode():
    assert C.char_count("# 役割\n- a *b*", markdown=False) == len("#役割-a*b*")


# ---- 見出し・アンカー ------------------------------------------------------------------
def test_parse_headings_ignores_code_fences():
    text = "# A\n```\n## not heading\n```\n## B ##\n~~~\n# no\n~~~\n"
    assert C.parse_headings(text) == [(1, 1, "A"), (5, 2, "B")]


def test_slugify_and_anchors():
    assert C.slugify("なぜ週次レビューは長引くのか") == "なぜ週次レビューは長引くのか"
    assert C.slugify("Hello, World!") == "hello-world"
    assert C.slugify("1. 要約") == "1-要約"
    assert C.slugify("決まり1：事前に一枚のメモを出す") == "決まり1事前に一枚のメモを出す"
    text = "###### [toTopPage](./README.md)\n## A\n## A\n"
    assert C.heading_anchors(text) == {"totoppage", "a", "a-1"}


def test_split_source():
    head, body, mark = C.split_source("H\n<!-- source-body:start -->\nB1\nB2\n")
    assert head == "H\n" and body == "B1\nB2\n" and mark == 2
    assert C.split_source("no marker\n")[2] is None


def test_section_text_excludes_trailing_separator():
    t = "## A\nx\n\n-----\n[toTop](#totoppage)\n## B\ny\n"
    assert C.section_text(t, "A", 2) == "## A\nx\n"
    assert C.section_text(t, "B", 2) == "## B\ny\n"
    assert C.section_text(t, "Z", 2) is None


def test_norm_for_quote():
    assert C.norm_for_quote("ＡＢＣ　１２３") == C.norm_for_quote("ABC 123")
    assert C.norm_for_quote("あ\n い") == "あい"


# ---- 理由コード・表示 -------------------------------------------------------------------
def test_reason_codes_all_have_meaning_and_next_step():
    want = {"NO_INPUT", "EMPTY_CONTENT", "MULTI_SOURCE", "DEST_EXISTS", "MISSING_OUT_FILE", "CHECK_FAILED", "UNEXPECTED"}
    assert set(C.REASON_MEANINGS) == want and set(C.NEXT_STEPS) == want


def test_report_stop_prints_last_three_lines(capsys):
    C.report_stop(C.StopReason("DEST_EXISTS", "もうある"))
    lines = capsys.readouterr().err.strip().splitlines()
    assert lines[0] == "[stop] もうある"
    assert lines[1].startswith("[next] ")
    assert lines[2] == "REASON=DEST_EXISTS"


def test_run_main_exit_codes():
    def stop():
        raise C.StopReason("NO_INPUT", "無い")

    def boom():
        raise ValueError("x")

    with pytest.raises(SystemExit) as e:
        C.run_main(stop)
    assert e.value.code == C.EXIT_FAIL == 1
    with pytest.raises(SystemExit) as e:
        C.run_main(boom)
    assert e.value.code == 1


def test_contract_epilog_lists_codes():
    s = C.contract_epilog(("NO_INPUT",), "結果")
    assert "0  成功" in s and "2  引数の誤り" in s and "NO_INPUT" in s and "REASON=<理由コード>" in s


def test_scripts_use_only_standard_library():
    import ast
    import sys as _sys
    std = set(_sys.stdlib_module_names)
    local = {p.stem for p in (ROOT / "plugins" / "ced-craft-explanation-docs" / "scripts").glob("*.py")}  # スクリプト同士の import
    for p in (ROOT / "plugins" / "ced-craft-explanation-docs" / "scripts").glob("*.py"):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [(node.module or "").split(".")[0]]
            for n in names:
                assert n in std or n in local, f"{p.name}: 標準ライブラリ以外を import している: {n}"


def test_fence_blocks_follow_commonmark_rules():
    lines = ["a", "~~~~", "```", "中", "```", "~~~~", "b", "```py", "x", "```"]
    assert C.fence_blocks(lines) == [(1, 5), (7, 9)]  # ~~~~ の中の ``` は文字として扱う
    assert C.fence_flags(lines) == [False, True, True, True, True, True, False, True, True, True]
    assert C.fence_blocks(["```", "あ"]) == [(0, None)]  # 閉じていない
    assert C.fence_blocks(["`````", "```", "`````"]) == [(0, 2)]  # 短い ``` では閉じない
    assert C.parse_headings("~~~~\n```\n# x\n```\n~~~~\n# y\n") == [(6, 1, "y")]
