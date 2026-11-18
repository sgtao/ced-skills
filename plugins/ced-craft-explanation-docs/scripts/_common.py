#!/usr/bin/env python3
"""_common.py — craft-explanation-docs のスクリプトが共通で使う土台（標準ライブラリのみ）。

ここに集めているもの:
  - 終了コード・理由コード・StopReason・run_main（失敗を「理由コード＋理由＋次の手段」で表示）
  - contract_epilog()        --help の末尾に出す「契約」（標準出力・終了コード・理由コード）
  - parse_frontmatter()      url-to-md の add_frontmatter.py が書く frontmatter を読む（読み取りはここだけ）
  - normalize_text() / normalize_body() / sha256_text()   改行・末尾の改行をそろえる、ハッシュ
  - char_count()             文字数の数え方（check_docs.py と assemble.py が同じ関数を使う）
  - Markdown の見出し・コードブロック・リンクの読み取り（slugify / parse_headings / split_source ほか）

終了コード:
  0 成功 / 1 失敗（理由コードつきの停止・想定外のエラー）/ 2 引数の誤り（argparse）
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import unicodedata

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

SKILL_VERSION = "0.0.6"

# 01_source.md の「ここから先が入力 MD の複製」という印（この行の後ろが複製）
SOURCE_BODY_MARKER = "<!-- source-body:start -->"

# 理由コード → ユーザーに勧める次の手段
NEXT_STEPS = {
    "NO_INPUT": "入力の Markdown のパスを確かめてください。URL だけのときは、先に url-to-md で Markdown にしてください。",
    "EMPTY_CONTENT": "入力の Markdown を確かめてください（空、または短すぎます）。",
    "MULTI_SOURCE": "入力は 1 つずつ頼んでください（v0.1.0 は 1 つの Markdown だけを扱います）。",
    "DEST_EXISTS": "続きから行うか、別の名前にするか、やめるかを、ユーザーに聞いてください（既定は置きません）。",
    "MISSING_OUT_FILE": "足りない out/ のファイルを作るステップを実行してから、assemble.py をやり直してください。",
    "CHECK_FAILED": "不合格の項目を、out/ の元のファイルで直して assemble.py をやり直してください（上限 3 回）。",
    "UNEXPECTED": "スクリプトは書き換えずに、この表示をそのまま報告してください。",
}

# 理由コード → 意味（--help に出す）
REASON_MEANINGS = {
    "NO_INPUT": "入力のファイル（フォルダ）が無い",
    "EMPTY_CONTENT": "本文が空、または短すぎる",
    "MULTI_SOURCE": "入力が 2 つ以上",
    "DEST_EXISTS": "作業フォルダが既にある（上書きしない）",
    "MISSING_OUT_FILE": "転記に要る out/ のファイルが無い",
    "CHECK_FAILED": "検査に不合格の項目がある",
    "UNEXPECTED": "上のどれでもない想定外のエラー",
}


class StopReason(Exception):
    """処理を続けられないことを、理由コードつきで伝える。"""

    def __init__(self, code: str, message: str, next_step: str | None = None,
                 exit_code: int = EXIT_FAIL):
        super().__init__(message)
        self.code = code
        self.message = message
        self.next_step = next_step if next_step is not None else NEXT_STEPS.get(code, "")
        self.exit_code = exit_code


def setup_stdio() -> None:
    """標準出力・標準エラーを UTF-8 にする（Windows の cp932 対策）。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def report_stop(e: StopReason) -> None:
    """StopReason を標準エラーに表示する（最後の 3 行が決まった形）。"""
    print(f"[stop] {e.message}", file=sys.stderr)
    if e.next_step:
        print(f"[next] {e.next_step}", file=sys.stderr)
    print(f"REASON={e.code}", file=sys.stderr)


def run_main(main_func) -> None:
    """main を包んで実行する。失敗はトレースバックではなく理由で伝える。

    環境変数 CRAFT_DEBUG=1 のときだけ、想定外のエラーのトレースバックを出す。
    """
    setup_stdio()
    try:
        main_func()
    except StopReason as e:
        report_stop(e)
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        print("[stop] 中断されました。", file=sys.stderr)
        sys.exit(130)
    except Exception as e:  # noqa: BLE001 - 最後の受け口
        if os.environ.get("CRAFT_DEBUG"):
            raise
        print(f"[error] 想定外のエラー: {type(e).__name__}: {e}", file=sys.stderr)
        print(f"[next] {NEXT_STEPS['UNEXPECTED']}（詳しい表示は環境変数 CRAFT_DEBUG=1）", file=sys.stderr)
        print("REASON=UNEXPECTED", file=sys.stderr)
        sys.exit(EXIT_FAIL)


def contract_epilog(reason_codes=(), stdout: str = "", exit_codes=None, notes=()) -> str:
    """--help の末尾（epilog）に出す、スクリプトの契約の文章を作る。"""
    if exit_codes is None:
        exit_codes = {
            0: "成功",
            1: "失敗（理由コードつき。REASON=UNEXPECTED は想定外。スクリプトは書き換えずに報告する）",
            2: "引数の誤り",
        }
    lines = ["標準出力:", f"  {stdout}（常に UTF-8）",
             "標準エラー:", "  進捗とログ（常に UTF-8）",
             "終了コード:"]
    lines += [f"  {code}  {text}" for code, text in exit_codes.items()]
    if reason_codes:
        lines += ["失敗時の表示（標準エラーの最後の 3 行）:",
                  "  [stop] 理由 / [next] 次の手段 / REASON=<理由コード>",
                  "  トレースバックは出さない（環境変数 CRAFT_DEBUG=1 のときだけ出す）",
                  "理由コード:"]
        width = max(len(c) for c in reason_codes)
        lines += [f"  {c.ljust(width)}  {REASON_MEANINGS[c]}" for c in reason_codes]
    lines += list(notes)
    return "\n".join(lines)


# ---- テキストの正規化・ハッシュ --------------------------------------------------
def normalize_text(text: str) -> str:
    """BOM を除き、改行を LF にそろえる（CRLF・CR → LF）。"""
    if text.startswith("﻿"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def normalize_body(text: str) -> str:
    """本文の保存・照合用の形。改行を LF にそろえ、末尾の改行を 1 つにそろえる。

    本文が空（空白だけ）なら空文字列を返す。途中の文字は一字も変えない。
    """
    text = normalize_text(text)
    if not text.strip():
        return ""
    return text.rstrip("\n") + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: str) -> str:
    """UTF-8 のファイルを読む（BOM を除き、改行を LF にそろえる）。"""
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        return normalize_text(f.read())


# ---- frontmatter（url-to-md の add_frontmatter.py が書く形）----------------------
# 項目の正は `add_frontmatter.py --help`。ここに無い項目は読まない。
FM_KEYS = ("title", "source_url", "source_format", "conversion",
           "channel", "published", "duration", "has_figures", "summary", "retrieved_at")
FM_REQUIRED = ("title", "source_url", "source_format")  # 無いときは警告（失敗にはしない）


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('\\"', '"')
    return value


def parse_frontmatter(text: str) -> tuple[dict, str, list[str]]:
    """frontmatter を読み、(項目の辞書, 本文, 警告のリスト) を返す。

    - frontmatter が無い・閉じていない → ({}, 全文, ["frontmatter なし"])（失敗にはしない）
    - 項目は FM_KEYS だけを読む。値は文字列（has_figures も "true"/"false" のまま）
    - 本文は frontmatter の直後から（一字も変えない。改行は LF にそろえる）
    """
    text = normalize_text(text)
    stripped = text.lstrip()
    if not stripped.startswith("---\n"):
        return {}, text, ["frontmatter なし"]
    lines = stripped.split("\n")
    end = None
    for i in range(1, len(lines)):
        if lines[i] == "---":
            end = i
            break
    if end is None:
        return {}, text, ["frontmatter なし（閉じる --- が無い）"]
    fm: dict[str, str] = {}
    for ln in lines[1:end]:
        m = re.match(r"^([A-Za-z_]+):[ \t]*(.*)$", ln)
        if m and m.group(1) in FM_KEYS:
            fm[m.group(1)] = _unquote(m.group(2))
    body = "\n".join(lines[end + 1:])
    warnings = [f"frontmatter の項目が無い: {k}" for k in FM_REQUIRED if not fm.get(k)]
    return fm, body, warnings


# ---- 文字数 ---------------------------------------------------------------------
def plain_text(text: str) -> str:
    """文字数を数えるための形にする。Markdown の記号と空白（改行を含む）を除く。

    除くもの: 行頭の `#`・`>`・`- `・`* `・`+ `・`1. `、リンクと画像の記法（文字だけ残す）、
    `*`・`_`・`` ` ``・`~`・`|`、すべての空白（全角空白を含む）。
    """
    text = normalize_text(text)
    lines = []
    for ln in text.split("\n"):
        ln = ln.strip()
        ln = re.sub(r"^(?:#{1,6}\s+|>\s?|[-*+]\s+|\d+\.\s+)", "", ln)
        lines.append(ln)
    t = "\n".join(lines)
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[*_`~|]", "", t)
    return re.sub(r"\s+", "", t)


def char_count(text: str, markdown: bool = True) -> int:
    """字数（Python の len。コードポイント数）。

    markdown=True: plain_text() で Markdown の記号と空白を除いて数える（要約・ポイントまとめなど）。
    markdown=False: 空白だけを除いて数える（コードブロックの中身。システムプロンプト用）。
    """
    if markdown:
        return len(plain_text(text))
    return len(re.sub(r"\s+", "", normalize_text(text)))


# ---- Markdown の読み取り ----------------------------------------------------------
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")


def fence_blocks(lines: list[str]) -> list[tuple[int, int | None]]:
    """コードブロックの (開く行, 閉じる行)（0 から。閉じていなければ None）のリスト。

    CommonMark の決まり: 閉じる行は、開く行と同じ文字（` か ~）で、同じかより長く、後ろに文字が無い。
    したがって、````（4 つ）や ~~~~ で囲んだ中の ``` は、ただの文字として扱う。
    """
    blocks: list[tuple[int, int | None]] = []
    open_at = None
    ch, n = "", 0
    for i, ln in enumerate(lines):
        m = _FENCE_RE.match(ln)
        if open_at is None:
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                open_at, ch, n = i, m.group(1)[0], len(m.group(1))
        elif m and m.group(1)[0] == ch and len(m.group(1)) >= n and not m.group(2).strip():
            blocks.append((open_at, i))
            open_at = None
    if open_at is not None:
        blocks.append((open_at, None))
    return blocks


def fence_flags(lines: list[str]) -> list[bool]:
    """各行が「コードブロックの中（区切りの行を含む）」かどうかのリスト。"""
    flags = [False] * len(lines)
    for a, b in fence_blocks(lines):
        for i in range(a, (b if b is not None else len(lines) - 1) + 1):
            flags[i] = True
    return flags


def heading_text(raw: str) -> str:
    """見出しの文字から、リンク・強調・インラインコードの記号を除く。"""
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", raw)
    t = re.sub(r"[*`]", "", t)
    return t.strip()


def parse_headings(text: str) -> list[tuple[int, int, str]]:
    """コードブロックの外の見出しを (行番号（1 から）, レベル, 見出しの文字) で返す。"""
    lines = normalize_text(text).split("\n")
    flags = fence_flags(lines)
    out = []
    for i, ln in enumerate(lines):
        if flags[i]:
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", ln)
        if m:
            out.append((i + 1, len(m.group(1)), heading_text(m.group(2))))
    return out


def slugify(title: str) -> str:
    """GitHub 流のアンカー名。小文字にし、記号を除き、空白を - にする（日本語はそのまま）。"""
    s = title.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def heading_anchors(text: str) -> set[str]:
    """ファイルの見出しから作れるアンカー名の集合（同名の見出しには -1, -2 を付ける）。"""
    seen: dict[str, int] = {}
    anchors = set()
    for _, _, title in parse_headings(text):
        base = slugify(title)
        n = seen.get(base, 0)
        anchors.add(base if n == 0 else f"{base}-{n}")
        seen[base] = n + 1
    return anchors


def split_source(text: str) -> tuple[str, str, int | None]:
    """01_source.md を (冒頭, 複製の本文, 印の行番号) に分ける。印が無ければ (全文, "", None)。

    本文は印の行の次の行から。冒頭には印の行までを含めない。
    """
    text = normalize_text(text)
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if ln.strip() == SOURCE_BODY_MARKER:
            return "\n".join(lines[:i]) + "\n", "\n".join(lines[i + 1:]), i + 1
    return text, "", None


def norm_for_quote(s: str) -> str:
    """引用の照合用の正規化。全角半角をそろえ（NFKC）、空白・改行をすべて除く。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s))


def section_text(text: str, title: str, level: int) -> str | None:
    """見出し（レベル・文字が一致）から、同じかより上のレベルの次の見出しの手前までのテキスト。

    見出し行を含む。見つからなければ None。末尾の空行は落とす。
    """
    lines = normalize_text(text).split("\n")
    heads = parse_headings(text)
    for idx, (ln, lv, t) in enumerate(heads):
        if lv == level and t == title:
            end = len(lines)
            for ln2, lv2, _ in heads[idx + 1:]:
                if lv2 <= level:
                    end = ln2 - 1
                    break
            chunk = lines[ln - 1:end]
            # 次の節の前に置く区切り（-----・[toTop]）は、この節に含めない
            while chunk and chunk[-1].strip() in ("", "-----", "[toTop](#totoppage)"):
                chunk.pop()
            return "\n".join(chunk) + "\n"
    return None


# ---- ひな形 ---------------------------------------------------------------------------
def fill_template(template: str, values: dict[str, str]) -> str:
    """ひな形の `{{名前}}` を values で置き換える。values に無い名前はそのまま残す
    （LLM が後で書く場所。残っていれば検査 C-4 が見つける）。"""
    def repl(m):
        key = m.group(1)
        return values[key] if key in values else m.group(0)
    return re.sub(r"\{\{(\w+)\}\}", repl, template)


def meta_bullets(items: list[tuple[str, str | None]]) -> str:
    """`- `key`: value` の行の並び。値が None の項目は行ごと出さない。"""
    return "\n".join(f"- `{k}`: {v}" for k, v in items if v is not None)
