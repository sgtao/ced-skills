#!/usr/bin/env python3
"""check_docs.py — 作業フォルダの最終ファイル 5 本を検査する（C-1〜C-11）。標準ライブラリのみ。

検査は読むだけで、何も書き換えない（直すのは LLM。検査を通すために字数・期待値・
検査の側を書き換えない）。項目の定義は references/output-formats.md の「検査項目」。

使い方:
  python3 check_docs.py <作業フォルダ> [--json] [--only C-1,C-6]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

from _common import (EXIT_FAIL, EXIT_OK, SOURCE_BODY_MARKER, StopReason, char_count,
                     contract_epilog, fence_blocks, fence_flags, heading_anchors, heading_text,
                     norm_for_quote, normalize_body, normalize_text, parse_headings,
                     read_text, run_main, section_text, sha256_text, split_source)

FINAL_FILES = [
    "README.md",
    "01_source.md",
    "02_explanation_memo.md",
    "11_question_and_answer.md",
    "12_LLM_prompts_as_guide.md",
]
MANIFEST = "out/00_manifest.json"
NAV1 = "###### [toTopPage](../README.md)"
NAV2 = "###### [toREADME](./README.md)"
SEP = ("-----", "[toTop](#totoppage)")

# 見出しの名前と順序（references/output-formats.md の §2）
README_H2 = ["セクション", "概要", "生成AIの総括", "本文", "解説メモ", "FAQ", "Proposed Prompts"]
MEMO_H3 = ["1. 要約", "2. 例え話", "3. セクション別の解説", "4. ユースケース", "5. 理解を深める質問"]
THEME_H3 = ["背景", "キー概念", "詳細解説", "注意点・限界", "ポイントまとめ", "確認の質問"]
PROMPT_H2 = ["システムプロンプト", "活用例：サンプル質問"]
LEVEL_H3 = ["初心者向け", "中級者向け", "上級者向け"]
H1_PREFIX = {
    "README.md": "資料：",
    "01_source.md": "本文：",
    "02_explanation_memo.md": "解説メモ：",
    "11_question_and_answer.md": "FAQ：",
    "12_LLM_prompts_as_guide.md": "Proposed Prompts：",
}

# 文字数の上限（§5-1）
LIMIT_SUMMARY = 400
LIMIT_POINT = 70
LIMIT_REFLECTION = 400
LIMIT_SYSTEM_PROMPT = 2000
LIMIT_README_OVERVIEW = 400
LIMIT_SOURCE_SUMMARY = 200

ITEMS = [
    ("C-1", "必須ファイル"),
    ("C-2", "見出し"),
    ("C-3", "out/ への参照"),
    ("C-4", "プレースホルダ"),
    ("C-5", "相対リンク"),
    ("C-6", "文字数"),
    ("C-7", "セクションの網羅"),
    ("C-8", "引用の照合"),
    ("C-9", "入力の保全"),
    ("C-10", "項目の一致"),
    ("C-11", "相互リンクと要約"),
]


def F(file, line, message):
    """検査の指摘 1 件（file・line は無ければ None）。"""
    return {"file": file, "line": line, "message": message}


# ---- 読み込み ---------------------------------------------------------------------
class Ctx:
    """作業フォルダの最終ファイルを読み込んだもの。無いファイルは None。"""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.texts: dict[str, str | None] = {}
        for name in FINAL_FILES:
            p = os.path.join(self.root, name)
            self.texts[name] = read_text(p) if os.path.isfile(p) else None
        self.manifest = None
        self.manifest_error = None
        mp = os.path.join(self.root, MANIFEST)
        if not os.path.isfile(mp):
            self.manifest_error = f"{MANIFEST} が無い"
        else:
            try:
                with open(mp, encoding="utf-8") as f:
                    self.manifest = json.load(f)
            except (OSError, ValueError) as e:
                self.manifest_error = f"{MANIFEST} を読めない: {e}"

    def present(self):
        return [n for n in FINAL_FILES if self.texts[n] is not None]

    def head(self, name: str) -> str | None:
        """検査の対象にする範囲。01_source.md は冒頭だけ（複製の本文は入力のもの）。"""
        t = self.texts.get(name)
        if t is None:
            return None
        if name == "01_source.md":
            return split_source(t)[0]
        return t

    def source_body(self) -> str | None:
        t = self.texts.get("01_source.md")
        if t is None:
            return None
        head, body, mark = split_source(t)
        return body if mark is not None else None


# ---- 節の読み取り -------------------------------------------------------------------
class Sec:
    __slots__ = ("level", "title", "line", "end")

    def __init__(self, level, title, line, end):
        self.level, self.title, self.line, self.end = level, title, line, end


def sections_of(text: str) -> tuple[list[Sec], list[str]]:
    """見出しごとの節（行番号は 1 から。end は次の同じかより上の見出しの行番号、無ければ末尾+1）。"""
    lines = normalize_text(text).split("\n")
    heads = parse_headings(text)
    secs = []
    for i, (ln, lv, t) in enumerate(heads):
        end = len(lines) + 1
        for ln2, lv2, _ in heads[i + 1:]:
            if lv2 <= lv:
                end = ln2
                break
        secs.append(Sec(lv, t, ln, end))
    return secs, lines


def sec_body(lines: list[str], sec: Sec) -> str:
    """節の本文（見出し行を除く。直後の節の前に置く区切りは含めない）。"""
    chunk = lines[sec.line:sec.end - 1]
    while chunk and chunk[-1].strip() in ("", SEP[0], SEP[1]):
        chunk.pop()
    return "\n".join(chunk).strip("\n")


def inside(secs: list[Sec], parent: Sec, level: int | None = None):
    """parent の中にある節（level を指定すればそのレベルだけ）。"""
    return [s for s in secs if s.line > parent.line and s.line < parent.end
            and (level is None or s.level == level)]


def find(secs, level, title):
    return [s for s in secs if s.level == level and s.title == title]


# ---- C-1 ---------------------------------------------------------------------------
def c1(ctx: Ctx):
    out = []
    for n in FINAL_FILES:
        if ctx.texts[n] is None:
            out.append(F(n, None, "ファイルが無い"))
    if ctx.manifest_error:
        out.append(F(MANIFEST, None, ctx.manifest_error))
    return out


# ---- C-2 ---------------------------------------------------------------------------
def _seq(out, file, secs, level, required, label=""):
    """required の見出しが、それぞれ 1 回ずつ、この順に出てくるか。"""
    last = 0
    for req in required:
        hits = [s for s in secs if s.level == level and s.title == req]
        if not hits:
            out.append(F(file, None, f"{label}見出し「{'#' * level} {req}」が無い"))
            continue
        if len(hits) > 1:
            out.append(F(file, hits[1].line, f"{label}見出し「{req}」が重複している"))
        if hits[0].line < last:
            out.append(F(file, hits[0].line, f"{label}見出し「{req}」の順序が違う"))
        last = max(last, hits[0].line)


def _separators(out, file, lines, secs, titles_by_level):
    """必須の `##` の前に `-----` と `[toTop](#totoppage)` があるか。"""
    for s in secs:
        if s.level != 2 or not titles_by_level(s.title):
            continue
        i = s.line - 1  # 見出しの行（0 から）
        if i < 2 or lines[i - 1].strip() != SEP[1] or lines[i - 2].strip() != SEP[0]:
            out.append(F(file, s.line, f"「## {s.title}」の前に `-----` と `[toTop](#totoppage)` が無い"))


def _nav_and_h1(out, file, text):
    lines = normalize_text(text).split("\n")
    if len(lines) < 2 or lines[0].strip() != NAV1:
        out.append(F(file, 1, f"1 行目がナビ（{NAV1}）でない"))
    if len(lines) < 2 or lines[1].strip() != NAV2:
        out.append(F(file, 2, f"2 行目がナビ（{NAV2}）でない"))
    heads = [h for h in parse_headings(text) if h[1] == 1]
    if not heads:
        out.append(F(file, None, "`# ` の題名の見出しが無い"))
    elif not heads[0][2].startswith(H1_PREFIX[file]):
        out.append(F(file, heads[0][0], f"題名の見出しが「# {H1_PREFIX[file]}…」でない"))


def _ends_with_sep(out, file, text):
    tail = [ln.strip() for ln in normalize_text(text).split("\n") if ln.strip()][-2:]
    if tail != list(SEP):
        out.append(F(file, None, "ファイルの末尾が `-----` と `[toTop](#totoppage)` でない"))


def c2(ctx: Ctx):
    out = []
    # README
    t = ctx.texts["README.md"]
    if t is not None:
        _nav_and_h1(out, "README.md", t)
        secs, lines = sections_of(t)
        _seq(out, "README.md", secs, 2, README_H2)
        _separators(out, "README.md", lines, secs, lambda x: x in README_H2)
        _ends_with_sep(out, "README.md", t)
    # 01_source.md（冒頭だけ）
    t = ctx.head("01_source.md")
    if t is not None:
        _nav_and_h1(out, "01_source.md", t)
        secs, lines = sections_of(t)
        h2 = [s for s in secs if s.level == 2]
        for s in h2:
            if s.title != "セクション目次":
                out.append(F("01_source.md", s.line, f"冒頭に `## {s.title}` がある（許すのは「セクション目次」だけ）"))
        if len([s for s in h2 if s.title == "セクション目次"]) > 1:
            out.append(F("01_source.md", None, "「セクション目次」が重複している"))
        _separators(out, "01_source.md", lines, secs, lambda x: x == "セクション目次")
        if ctx.texts["01_source.md"] is not None and split_source(ctx.texts["01_source.md"])[2] is None:
            out.append(F("01_source.md", None, f"本文の開始の印 {SOURCE_BODY_MARKER} が無い"))
    # 02
    t = ctx.texts["02_explanation_memo.md"]
    if t is not None:
        f = "02_explanation_memo.md"
        _nav_and_h1(out, f, t)
        secs, lines = sections_of(t)
        is_req = lambda x: x in ("解説", "活用案") or x.startswith("テーマ：")
        _separators(out, f, lines, secs, is_req)
        _ends_with_sep(out, f, t)
        kai = find(secs, 2, "解説")
        kat = find(secs, 2, "活用案")
        themes = [s for s in secs if s.level == 2 and s.title.startswith("テーマ：")]
        if not kai:
            out.append(F(f, None, "見出し「## 解説」が無い"))
        if len(kai) > 1:
            out.append(F(f, kai[1].line, "見出し「解説」が重複している"))
        if not kat:
            out.append(F(f, None, "見出し「## 活用案」が無い"))
        if len(kat) > 1:
            out.append(F(f, kat[1].line, "見出し「活用案」が重複している"))
        if not themes:
            out.append(F(f, None, "見出し「## テーマ：<グループ名>」が 1 つも無い"))
        names = [s.title for s in themes]
        for s in themes:
            if not s.title[len("テーマ："):].strip():
                out.append(F(f, s.line, "「## テーマ：」のグループ名が空"))
        if len(set(names)) != len(names):
            out.append(F(f, None, "「## テーマ：」のグループ名が重複している"))
        if kai and themes and themes[0].line < kai[0].line:
            out.append(F(f, themes[0].line, "「## テーマ：」が「## 解説」より前にある"))
        if kat and themes and themes[-1].line > kat[0].line:
            out.append(F(f, kat[0].line, "「## 活用案」が「## テーマ：」より前にある"))
        if kai:
            sub = inside(secs, kai[0])
            _seq(out, f, sub, 3, MEMO_H3, "「解説」の中の ")
            q = find(sub, 3, "5. 理解を深める質問")
            if q:
                n = len(inside(secs, q[0], 4))
                if n != 5:
                    out.append(F(f, q[0].line, f"「5. 理解を深める質問」の `####`（各問の回答）が {n} 個（5 個が必要）"))
        for th in themes:
            _seq(out, f, inside(secs, th), 3, THEME_H3, f"「{th.title}」の中の ")
        if kat:
            cases = [s for s in inside(secs, kat[0], 3) if re.match(r"^案[1-3]", s.title)]
            if [s.title[:2] for s in cases] != ["案1", "案2", "案3"]:
                out.append(F(f, kat[0].line, "「## 活用案」に `### 案1`・`### 案2`・`### 案3` が順に 3 つ必要"))
    # 11
    t = ctx.texts["11_question_and_answer.md"]
    if t is not None:
        f = "11_question_and_answer.md"
        _nav_and_h1(out, f, t)
        secs, lines = sections_of(t)
        groups = [s for s in secs if s.level == 2 and s.title.startswith("FAQ｜グループ")]
        _separators(out, f, lines, secs, lambda x: x.startswith("FAQ｜グループ"))
        _ends_with_sep(out, f, t)
        if not groups:
            out.append(F(f, None, "見出し「## FAQ｜グループN：<グループ名>」が 1 つも無い"))
        for i, g in enumerate(groups, 1):
            m = re.match(r"^FAQ｜グループ(\d+)：(.+)$", g.title)
            if not m:
                out.append(F(f, g.line, "見出しが「FAQ｜グループN：<グループ名>」の形でない"))
            elif int(m.group(1)) != i:
                out.append(F(f, g.line, f"グループの番号が {i} でない（{m.group(1)}）"))
        number = 0
        for g in groups:
            qs = inside(secs, g, 3)
            if not qs:
                out.append(F(f, g.line, f"「{g.title}」に `### <番号>. <題>` が 1 つも無い"))
            for q in qs:
                number += 1
                m = re.match(r"^(\d+)\.\s*\S", q.title)
                if not m:
                    out.append(F(f, q.line, "FAQ の見出しが「### <番号>. <題>」の形でない"))
                elif int(m.group(1)) != number:
                    out.append(F(f, q.line, f"FAQ の通し番号が {number} でない（{m.group(1)}）"))
                body = "\n".join(lines[q.line:q.end - 1])
                for label in ("質問", "回答", "具体例", "該当箇所"):
                    if not re.search(r"\*\*" + label + r"\*\*", body):
                        out.append(F(f, q.line, f"FAQ「{q.title}」に **{label}** が無い"))
    # 12
    t = ctx.texts["12_LLM_prompts_as_guide.md"]
    if t is not None:
        f = "12_LLM_prompts_as_guide.md"
        _nav_and_h1(out, f, t)
        secs, lines = sections_of(t)
        _seq(out, f, secs, 2, PROMPT_H2)
        _separators(out, f, lines, secs, lambda x: x in PROMPT_H2)
        _ends_with_sep(out, f, t)
        sp = find(secs, 2, "システムプロンプト")
        if sp:
            opens = len(fence_blocks(lines[sp[0].line:sp[0].end - 1]))
            if opens != 1:
                out.append(F(f, sp[0].line, f"「システムプロンプト」にコードブロックが {opens} 個（1 個が必要）"))
        ex = find(secs, 2, "活用例：サンプル質問")
        if ex:
            _seq(out, f, inside(secs, ex[0]), 3, LEVEL_H3, "「活用例：サンプル質問」の中の ")
    return out


# ---- C-3 / C-4 ---------------------------------------------------------------------
_OUT_REF = re.compile(r"(?<![\w.-])(?:\./)?out[/\\]")


def c3(ctx: Ctx):
    out = []
    for n in ctx.present():
        text = ctx.head(n)
        for i, ln in enumerate(normalize_text(text).split("\n"), 1):
            if _OUT_REF.search(ln):
                out.append(F(n, i, "out/ への参照がある: " + ln.strip()[:60]))
    return out


_PLACEHOLDER = re.compile(r"\{\{|\}\}|＜[^＞\n]{0,80}＞|\bTODO\b")


def c4(ctx: Ctx):
    out = []
    for n in ctx.present():
        text = ctx.head(n)
        lines = normalize_text(text).split("\n")
        flags = fence_flags(lines)
        # 02・11 のコードブロックは本文のコードの引用なので見ない（12 のシステムプロンプトは見る）
        skip_fence = n in ("02_explanation_memo.md", "11_question_and_answer.md")
        for i, ln in enumerate(lines):
            if skip_fence and flags[i]:
                continue
            m = _PLACEHOLDER.search(ln)
            if m:
                out.append(F(n, i + 1, f"プレースホルダが残っている: {m.group(0)}"))
    return out


# ---- C-5 ---------------------------------------------------------------------------
_LINK = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)\)")


def c5(ctx: Ctx):
    out = []
    anchors_cache: dict[str, set[str]] = {}

    def anchors(name):
        if name not in anchors_cache:
            t = ctx.texts.get(name)
            anchors_cache[name] = heading_anchors(t) if t is not None else set()
        return anchors_cache[name]

    for n in ctx.present():
        text = ctx.head(n)
        lines = normalize_text(text).split("\n")
        flags = fence_flags(lines)
        for i, ln in enumerate(lines):
            if flags[i] or i == 0:  # 1 行目の toTopPage は対象外
                continue
            ln2 = re.sub(r"`[^`]*`", "", ln)
            for m in _LINK.finditer(ln2):
                target = m.group(2)
                if re.match(r"^(https?:|mailto:)", target):
                    continue
                path, _, frag = target.partition("#")
                if not path:
                    dest = n
                else:
                    full = os.path.normpath(os.path.join(os.path.dirname(os.path.join(ctx.root, n)), path))
                    rel = os.path.relpath(full, ctx.root)
                    if rel.startswith(".."):
                        out.append(F(n, i + 1, f"作業フォルダの外を指している: {target}"))
                        continue
                    if not os.path.exists(full):
                        if rel.replace(os.sep, "/") not in FINAL_FILES:  # 最終ファイルが無いことは C-1 が報告する
                            out.append(F(n, i + 1, f"リンク先のファイルが無い: {target}"))
                        continue
                    dest = rel.replace(os.sep, "/")
                if frag:
                    if dest not in FINAL_FILES:
                        continue  # 最終ファイル以外の見出しは調べない
                    if ctx.texts.get(dest) is None:
                        continue  # ファイルが無いことは C-1 が報告する
                    if frag not in anchors(dest):
                        out.append(F(n, i + 1, f"リンク先の見出しが無い: {target}"))
    return out


# ---- C-6 ---------------------------------------------------------------------------
def c6(ctx: Ctx):
    out = []
    t = ctx.texts["README.md"]
    if t is not None:
        secs, lines = sections_of(t)
        for s in find(secs, 2, "概要"):
            n = char_count(sec_body(lines, s))
            if n > LIMIT_README_OVERVIEW:
                out.append(F("README.md", s.line, f"概要が {n} 字（上限 {LIMIT_README_OVERVIEW} 字）"))
    t = ctx.head("01_source.md")
    if t is not None:
        for ln_no, ln in enumerate(normalize_text(t).split("\n"), 1):
            if ln.startswith("> 要約："):
                n = char_count(ln[len("> 要約："):])
                if n > LIMIT_SOURCE_SUMMARY:
                    out.append(F("01_source.md", ln_no, f"要約が {n} 字（上限 {LIMIT_SOURCE_SUMMARY} 字）"))
    t = ctx.texts["02_explanation_memo.md"]
    if t is not None:
        f = "02_explanation_memo.md"
        secs, lines = sections_of(t)
        for s in find(secs, 3, "1. 要約"):
            n = char_count(sec_body(lines, s))
            if n > LIMIT_SUMMARY:
                out.append(F(f, s.line, f"要約が {n} 字（上限 {LIMIT_SUMMARY} 字）"))
        for s in secs:
            if s.level == 3 and s.title == "ポイントまとめ":
                n = char_count(sec_body(lines, s))
                if n > LIMIT_POINT:
                    out.append(F(f, s.line, f"ポイントまとめが {n} 字（上限 {LIMIT_POINT} 字）"))
        for kat in find(secs, 2, "活用案"):
            for s in inside(secs, kat, 3):
                if not re.match(r"^案[1-3]", s.title):
                    continue
                body = sec_body(lines, s).rstrip()
                m = re.search(r"（\s*(\d+)\s*字）\s*$", body)
                if not m:
                    out.append(F(f, s.line, f"「{s.title}」の末尾に「（N字）」が無い"))
                    measured = char_count(body)
                else:
                    measured = char_count(body[:m.start()])
                    if int(m.group(1)) != measured:
                        out.append(F(f, s.line, f"「{s.title}」の末尾の字数が実測と違う（書いてある数 {m.group(1)}／実測 {measured}）"))
                if measured > LIMIT_REFLECTION:
                    out.append(F(f, s.line, f"「{s.title}」が {measured} 字（上限 {LIMIT_REFLECTION} 字）"))
    t = ctx.texts["12_LLM_prompts_as_guide.md"]
    if t is not None:
        f = "12_LLM_prompts_as_guide.md"
        secs, lines = sections_of(t)
        for s in find(secs, 2, "システムプロンプト"):
            seg = lines[s.line:s.end - 1]
            blocks = fence_blocks(seg)
            inner = seg[blocks[0][0] + 1:blocks[0][1]] if blocks and blocks[0][1] is not None else []
            n = char_count("\n".join(inner), markdown=False)
            if n > LIMIT_SYSTEM_PROMPT:
                out.append(F(f, s.line, f"システムプロンプトが {n} 字（上限 {LIMIT_SYSTEM_PROMPT} 字）"))
    return out


# ---- セクション一覧（README と 01_source.md の目次）----------------------------------
_ITEM = re.compile(r"^- (\d+) : (.+)$")


def parse_section_items(text: str, title: str):
    """`## <title>` の下の `- N : 名前[ ｜ 詳細]` を [(番号, 名前, 詳細, 行番号)] で返す。
    リンクは文字だけにする。節が無ければ None。"""
    if text is None:
        return None
    secs, lines = sections_of(text)
    hits = find(secs, 2, title)
    if not hits:
        return None
    items = []
    for i in range(hits[0].line, hits[0].end - 1):
        m = _ITEM.match(lines[i].strip())
        if m:
            raw = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(2)).strip()
            name, _, detail = raw.partition(" ｜ ")
            items.append((int(m.group(1)), name.strip(), detail.strip(), i + 1))
    return items


def c7(ctx: Ctx):
    out = []
    items = parse_section_items(ctx.texts["README.md"], "セクション") or []
    if not items:
        return out  # 分割なし（対象が無い）
    memo = ctx.texts["02_explanation_memo.md"]
    faq = ctx.texts["11_question_and_answer.md"]
    memo_part = None
    if memo is not None:
        secs, lines = sections_of(memo)
        hit = find(secs, 3, "3. セクション別の解説")
        memo_part = norm_for_quote(sec_body(lines, hit[0])) if hit else ""
    faq_part = None
    if faq is not None:
        faq_part = norm_for_quote("\n".join(
            ln for ln in normalize_text(faq).split("\n") if re.search(r"\*\*該当箇所\*\*", ln)))
    for num, name, _, line in items:
        key = norm_for_quote(name)
        if memo_part is not None and key not in memo_part:
            out.append(F("02_explanation_memo.md", None, f"セクション{num}「{name}」が「3. セクション別の解説」に出てこない"))
        if faq_part is not None and key not in faq_part:
            out.append(F("11_question_and_answer.md", None, f"セクション{num}「{name}」が「該当箇所」に出てこない"))
    return out


# ---- C-8 ---------------------------------------------------------------------------
_QUOTE = re.compile(r"「([^」]+)」")
_EVIDENCE = re.compile(r"(?:\*\*)?(?:根拠|該当箇所)(?:\*\*)?\s*[：:]")  # 根拠の行（太字でもよい）


def c8(ctx: Ctx):
    out = []
    body = ctx.source_body()
    if body is None:
        if ctx.texts["01_source.md"] is not None:
            out.append(F("01_source.md", None, "本文を取り出せないため、引用を照合できない"))
        return out
    nbody = norm_for_quote(body)
    for n in ("02_explanation_memo.md", "11_question_and_answer.md"):
        t = ctx.texts[n]
        if t is None:
            continue
        lines = normalize_text(t).split("\n")
        flags = fence_flags(lines)
        for i, ln in enumerate(lines):
            if flags[i] or not _EVIDENCE.search(ln):
                continue
            for q in _QUOTE.findall(ln):
                for part in re.split(r"…（中略）…", q):
                    part = part.strip().strip("…").strip()
                    if part and norm_for_quote(part) not in nbody:
                        out.append(F(n, i + 1, "引用が 01_source.md の本文に無い: 「" + part[:40] + ("…" if len(part) > 40 else "") + "」"))
    return out


# ---- C-9 ---------------------------------------------------------------------------
def c9(ctx: Ctx):
    out = []
    t = ctx.texts["01_source.md"]
    if t is not None:
        head, body, mark = split_source(t)
        if mark is None:
            out.append(F("01_source.md", None, f"本文の開始の印 {SOURCE_BODY_MARKER} が無い"))
        elif ctx.manifest is None:
            pass  # manifest が無い・読めないことは C-1 が報告する
        else:
            want = ctx.manifest.get("body_sha256")
            got = sha256_text(normalize_body(body))
            if not want:
                out.append(F(MANIFEST, None, "body_sha256 が無い"))
            elif got != want:
                out.append(F("01_source.md", mark, "本文が入力の複製と違う（ハッシュが manifest と一致しない）"))
    # スキルが作っていない節（利用者が足した節）が前後で同じか
    if ctx.manifest:
        for fs in ctx.manifest.get("foreign_sections", []) or []:
            name, title, level, want = fs.get("file"), fs.get("heading"), fs.get("level", 2), fs.get("sha256")
            text = ctx.texts.get(name) if name in FINAL_FILES else None
            if text is None:
                out.append(F(name, None, f"スキルが作っていない節「{title}」を含むファイルが無い"))
                continue
            sec = section_text(text, title, level)
            if sec is None:
                out.append(F(name, None, f"スキルが作っていない節「{title}」が消えている"))
            elif sha256_text(normalize_body(sec)) != want:
                out.append(F(name, None, f"スキルが作っていない節「{title}」が書き換えられている"))
    return out


# ---- C-10 --------------------------------------------------------------------------
_BULLET = re.compile(r"^- `([a-z_]+)`: ?(.*)$")


def header_bullets(text: str | None) -> dict:
    """題名の下の `- `key`: value` の箇条書き（最初の `##` か本文の印の手前まで）。"""
    res = {}
    if text is None:
        return res
    for ln in normalize_text(text).split("\n"):
        if ln.startswith("## ") or ln.strip() == SOURCE_BODY_MARKER:
            break
        m = _BULLET.match(ln.strip())
        if m:
            res[m.group(1)] = m.group(2).strip()
    return res


def h1_title(text: str | None, file: str) -> str | None:
    if text is None:
        return None
    for _, lv, t in parse_headings(text):
        if lv == 1:
            return t[len(H1_PREFIX[file]):].strip() if t.startswith(H1_PREFIX[file]) else None
    return None


def c10(ctx: Ctx):
    out = []
    titles, urls = {}, {}
    for n in ctx.present():
        b = header_bullets(ctx.head(n))
        titles[n] = b.get("title", "")
        urls[n] = b.get("url", "") or None
        if not titles[n]:
            out.append(F(n, None, "題名の下に `- `title`: …` が無い"))
        h1 = h1_title(ctx.head(n), n)
        if titles[n] and h1 is not None and h1 != titles[n]:
            out.append(F(n, None, f"`# {H1_PREFIX[n]}` の題名（{h1}）と `title`（{titles[n]}）が違う"))
    vals = {v for v in titles.values() if v}
    if len(vals) > 1:
        out.append(F(None, None, "5 本の `title` が同じでない: " + " / ".join(f"{n}={v}" for n, v in titles.items())))
    uvals = {v for v in urls.values()}
    if len(uvals) > 1:
        out.append(F(None, None, "5 本の `url` が同じでない: " + " / ".join(f"{n}={v or '（なし）'}" for n, v in urls.items())))
    # README のセクション一覧と 01_source.md の目次
    r_items = parse_section_items(ctx.texts["README.md"], "セクション")
    s_head = ctx.head("01_source.md")
    s_items = parse_section_items(s_head, "セクション目次")
    if ctx.texts["README.md"] is not None and s_head is not None:
        a = [(i, nm, d) for i, nm, d, _ in (r_items or [])]
        b = [(i, nm, d) for i, nm, d, _ in (s_items or [])]
        if a != b:
            out.append(F("README.md", None, f"README のセクション一覧（{len(a)} 件）と 01_source.md のセクション目次（{len(b)} 件）が同じでない"))
    # グループ名（02 のテーマと 11 の FAQ グループ）
    memo, faq = ctx.texts["02_explanation_memo.md"], ctx.texts["11_question_and_answer.md"]
    if memo is not None and faq is not None:
        g1 = [t[len("テーマ："):].strip() for _, lv, t in parse_headings(memo) if lv == 2 and t.startswith("テーマ：")]
        g2 = []
        for _, lv, t in parse_headings(faq):
            m = re.match(r"^FAQ｜グループ\d+：(.+)$", t) if lv == 2 else None
            if m:
                g2.append(m.group(1).strip())
        if g1 != g2:
            out.append(F("11_question_and_answer.md", None, f"グループ名が 02 のテーマと同じでない（02: {g1}／11: {g2}）"))
    return out


# ---- C-11 --------------------------------------------------------------------------
def c11(ctx: Ctx):
    out = []
    t = ctx.head("01_source.md")
    if t is not None:
        if not re.search(r"\[README\.md\]\(\./README\.md\)", t):
            out.append(F("01_source.md", None, "冒頭に README へのリンク `[README.md](./README.md)` が無い"))
        summ = [(i, ln) for i, ln in enumerate(normalize_text(t).split("\n"), 1) if ln.startswith("> 要約：")]
        if not summ:
            out.append(F("01_source.md", None, "冒頭に `> 要約：…` が無い"))
        else:
            n = char_count(summ[0][1][len("> 要約："):])
            if n == 0:
                out.append(F("01_source.md", summ[0][0], "要約が空"))
            elif n > LIMIT_SOURCE_SUMMARY:
                out.append(F("01_source.md", summ[0][0], f"要約が {n} 字（上限 {LIMIT_SOURCE_SUMMARY} 字）"))
    r = ctx.texts["README.md"]
    if r is not None:
        secs, lines = sections_of(r)
        hit = find(secs, 2, "本文")
        if not hit:
            out.append(F("README.md", None, "「## 本文」が無い"))
        elif not re.search(r"\]\(\./01_source\.md(#[^)]*)?\)", sec_body(lines, hit[0])):
            out.append(F("README.md", hit[0].line, "「## 本文」に 01_source.md へのリンクが無い"))
    return out


CHECKS = {"C-1": c1, "C-2": c2, "C-3": c3, "C-4": c4, "C-5": c5, "C-6": c6,
          "C-7": c7, "C-8": c8, "C-9": c9, "C-10": c10, "C-11": c11}


def run_checks(root: str, only=None) -> dict:
    """検査を実行し、{"schema", "folder", "passed", "summary", "items": [...]} を返す。"""
    ctx = Ctx(root)
    items = []
    for cid, name in ITEMS:
        if only and cid not in only:
            continue
        findings = CHECKS[cid](ctx)
        items.append({"id": cid, "name": name,
                      "status": "FAIL" if findings else "PASS",
                      "findings": findings})
    npass = sum(1 for i in items if i["status"] == "PASS")
    return {"schema": 1, "folder": ctx.root, "passed": npass == len(items),
            "summary": {"pass": npass, "fail": len(items) - npass}, "items": items}


def format_report(result: dict) -> str:
    lines = [f"check_docs: {result['folder']}"]
    for it in result["items"]:
        lines.append(f"{it['status']}  {it['id'].ljust(4)} {it['name']}")
        for fd in it["findings"]:
            where = fd["file"] or "-"
            if fd["line"]:
                where += f":{fd['line']}"
            lines.append(f"       {where}  {fd['message']}")
    s = result["summary"]
    lines.append(f"結果: {s['pass']} PASS / {s['fail']} FAIL")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "作業フォルダの最終ファイル 5 本を検査する（C-1〜C-11）。読むだけで、何も書き換えない。\n"
            "\n"
            "入力:\n"
            "  <folder>  作業フォルダ（README.md・01_source.md・02_explanation_memo.md・\n"
            "            11_question_and_answer.md・12_LLM_prompts_as_guide.md・out/00_manifest.json）\n"
            "検査項目: C-1 必須ファイル／C-2 見出し／C-3 out/ への参照／C-4 プレースホルダ／\n"
            "          C-5 相対リンク／C-6 文字数／C-7 セクションの網羅／C-8 引用の照合／\n"
            "          C-9 入力の保全／C-10 項目の一致／C-11 相互リンクと要約\n"
            "（読み合わせの項目 R-1〜R-4 は LLM が行う。このスクリプトでは確かめない）"),
        epilog=contract_epilog(
            ("NO_INPUT", "CHECK_FAILED"),
            "項目ごとの PASS／FAIL と場所（--json のときは JSON。形は references/output-formats.md）",
            notes=["--json の形: {schema, folder, passed, summary:{pass,fail}, "
                   "items:[{id, name, status, findings:[{file, line, message}]}]}"]))
    ap.add_argument("folder", help="作業フォルダ")
    ap.add_argument("--json", action="store_true", help="結果を JSON で出す")
    ap.add_argument("--only", default=None, metavar="C-1,C-6",
                    help="指定した項目だけ検査する（カンマ区切り）")
    args = ap.parse_args()

    if not os.path.isdir(args.folder):
        raise StopReason("NO_INPUT", f"作業フォルダが見つかりません: {args.folder}",
                         "作業フォルダのパスを確かめてください。")
    only = None
    if args.only:
        only = {x.strip().upper() for x in args.only.split(",") if x.strip()}
        unknown = only - set(CHECKS)
        if unknown:
            ap.error(f"知らない項目: {', '.join(sorted(unknown))}（C-1〜C-11）")

    result = run_checks(args.folder, only)
    if args.json:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(format_report(result) + "\n")
    if not result["passed"]:
        failed = [i["id"] for i in result["items"] if i["status"] == "FAIL"]
        raise StopReason("CHECK_FAILED", f"検査に不合格の項目があります: {', '.join(failed)}")


if __name__ == "__main__":
    run_main(main)
