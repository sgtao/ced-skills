"""P0: 入力の見本が、url-to-md の frontmatter の形になっていることを確かめる。

このファイルは見本の「形」だけを見る。frontmatter の読み取りそのもの
（scripts/_common.py）は P1 で作り、そちらのテストで確かめる。
ここでは標準ライブラリだけの簡単な読み取りを使う（_common.py に依存しない）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

INPUTS = Path(__file__).parent / "fixtures" / "inputs"

# add_frontmatter.py が必ず書く項目（順序も同じ）
BASE_KEYS = ["title", "source_url", "source_format"]
TAIL_KEYS = ["has_figures", "summary", "retrieved_at"]
YOUTUBE_KEYS = ["channel", "published", "duration"]
FORMATS = {"html", "pdf", "docx", "xlsx", "pptx", "youtube"}
CONVERSIONS = {"pdf", "direct", "model-read"}

WITH_FRONTMATTER = [
    "video.md",
    "video-nochapter.md",
    "article.md",
    "document.md",
    "document-direct.md",
]
ALL = WITH_FRONTMATTER + ["plain.md"]


def split_frontmatter(text: str):
    """(frontmatter の行のリスト, 本文) を返す。frontmatter が無ければ (None, text)。"""
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None, text
    end = text.index("\n---\n", 4)
    return text[4:end].split("\n"), text[end + 5:]


def keys_of(lines):
    return [ln.split(":", 1)[0] for ln in lines if re.match(r"^[a-z_]+:", ln)]


def value_of(lines, key):
    for ln in lines:
        if ln.startswith(key + ":"):
            return ln.split(":", 1)[1].strip().strip('"')
    return None


def read(name):
    return (INPUTS / name).read_text(encoding="utf-8")


def test_all_fixtures_exist():
    for name in ALL:
        assert (INPUTS / name).is_file(), name


@pytest.mark.parametrize("name", WITH_FRONTMATTER)
def test_frontmatter_has_url_to_md_keys(name):
    fm, body = split_frontmatter(read(name))
    assert fm is not None, f"{name}: frontmatter が無い"
    keys = keys_of(fm)
    for k in BASE_KEYS + TAIL_KEYS:
        assert k in keys, f"{name}: {k} が無い"
    # add_frontmatter.py の順序: title, source_url, source_format, ...(任意)..., has_figures, summary, retrieved_at
    assert keys[:3] == BASE_KEYS
    assert keys[-3:] == TAIL_KEYS
    assert value_of(fm, "source_format") in FORMATS
    assert value_of(fm, "has_figures") in {"true", "false"}
    assert len(value_of(fm, "summary")) <= 200
    assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$", value_of(fm, "retrieved_at"))
    assert body.strip(), f"{name}: 本文が空"


@pytest.mark.parametrize("name", ["video.md", "video-nochapter.md"])
def test_video_fixtures_have_youtube_keys(name):
    fm, body = split_frontmatter(read(name))
    assert value_of(fm, "source_format") == "youtube"
    for k in YOUTUBE_KEYS:
        assert k in keys_of(fm), f"{name}: {k} が無い"
    assert "conversion" not in keys_of(fm)
    # 本文の形: # タイトル → ## 概要 → ## Transcript（段落頭に **[MM:SS]**）
    heads = re.findall(r"^## (.+)$", body, re.M)
    assert heads == ["概要", "Transcript"]
    stamps = re.findall(r"^\*\*\[(\d\d:\d\d)\]\*\* ", body, re.M)
    assert len(stamps) >= 8
    assert stamps == sorted(stamps), "タイムスタンプが昇順でない"


def test_video_has_chapters_and_nochapter_does_not():
    chapter_line = re.compile(r"^\d+:\d\d .+$", re.M)
    with_ch = split_frontmatter(read("video.md"))[1]
    without = split_frontmatter(read("video-nochapter.md"))[1]
    assert len(chapter_line.findall(with_ch)) >= 4
    assert "チャプター" in with_ch
    assert not chapter_line.findall(without)
    assert "チャプター" not in without
    # チャプターの有無以外は同じ文章（Transcript が一致する）
    assert with_ch.split("## Transcript")[1] == without.split("## Transcript")[1]


def test_video_transcript_has_no_punctuation_and_known_misrecognitions():
    body = split_frontmatter(read("video.md"))[1]
    transcript = body.split("## Transcript")[1]
    assert "、" not in transcript and "。" not in transcript
    for wrong in ["在庫回転立", "月症", "減価率", "店卸し", "初注点"]:
        assert wrong in transcript, wrong


def test_chapter_times_match_transcript_paragraphs():
    """概要欄のチャプターの時刻が、字幕の段落頭の時刻のどれかと一致する。"""
    body = split_frontmatter(read("video.md"))[1]
    chapters = re.findall(r"^(\d+):(\d\d) .+$", body, re.M)
    stamps = set(re.findall(r"^\*\*\[(\d\d:\d\d)\]\*\*", body, re.M))
    for m, s in chapters:
        assert f"{int(m):02d}:{s}" in stamps, f"{m}:{s} に対応する段落が無い"


def test_article_fixture_shape():
    fm, body = split_frontmatter(read("article.md"))
    assert value_of(fm, "source_format") == "html"
    assert "conversion" not in keys_of(fm)
    assert len(re.findall(r"^## ", body, re.M)) >= 4
    assert body.count("```") == 2  # コードブロックが 1 つ
    assert re.search(r"^\|.+\|$", body, re.M)  # 表がある


def test_document_fixtures_shape():
    fm, body = split_frontmatter(read("document.md"))
    assert value_of(fm, "source_format") == "pdf"
    assert value_of(fm, "conversion") == "pdf"
    assert value_of(fm, "has_figures") == "true"
    assert "<svg" in body

    fm, body = split_frontmatter(read("document-direct.md"))
    assert value_of(fm, "source_format") == "pptx"
    assert value_of(fm, "conversion") == "direct"
    assert len(re.findall(r"<!-- Slide number: \d+ -->", body)) >= 4
    assert "## 補足: 画面表示から得られる情報" in body
    assert "この変換で再現できなかったもの" in body


def test_plain_has_no_frontmatter_and_no_sections():
    fm, body = split_frontmatter(read("plain.md"))
    assert fm is None
    assert body.startswith("# ")
    assert not re.search(r"^##+ ", body, re.M)  # セクション見出しが無い


@pytest.mark.parametrize("name", ALL)
def test_fixtures_are_original_and_utf8_lf(name):
    raw = (INPUTS / name).read_bytes()
    assert b"\r" not in raw, "LF にそろえる"
    text = raw.decode("utf-8")
    # 自作の見本であること: GLOBIS の語を入れない
    for word in ["GLOBIS", "グロービス", "講座ID", "学びエージェント"]:
        assert word not in text, f"{name}: {word}"
