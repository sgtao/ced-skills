#!/usr/bin/env python3
"""出力フォルダ名の候補を 3 つ作る（標準ライブラリだけ）。V3-M2・PLAN.md の D13・D15。

名前の形（D13）: `YYMMDD_<英小文字と数字と ->`。`_` の後ろは 40 文字以内で、単語の切れ目で切る。
英訳・要約の候補は呼び出し側（Claude）が作って渡す。このスクリプトは、形を整え、重複と既にある名前を避け、
候補を 3 つにそろえる。日本語など英字以外の文字は、この段階では捨てる（英訳を先に渡す約束）。

使い方:
  python3 ced_name.py --date 261118 --title "Claude Code Plugin Guide" --title "cc plugin basics" --existing <出力先>
  同じ入力の既存フォルダがあるとき（collect_sources.py plan の resumable）: --resume <既存のフォルダ名> を足す。
  既存の名前は避けずに、先頭の候補にする（再開。D18）。それ以外の既存の名前は、これまでどおり避ける。
  → JSON の配列（3 件）を標準出力へ
終了コード: 0＝成功、2＝引数が不正（日付の形など）
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

MAX_BODY = 40
COUNT = 3
FALLBACK = "source"
DATE_RE = re.compile(r"^[0-9]{6}$")
NAME_RE = re.compile(r"^[0-9]{6}_[a-z0-9]+(-[a-z0-9]+)*$")  # D13


def check_date(date: str) -> None:
    if not DATE_RE.match(date):
        raise ValueError(f"日付は YYMMDD の 6 桁（実際: {date!r}）")
    try:
        datetime.strptime(date, "%y%m%d")
    except ValueError as e:
        raise ValueError(f"存在しない日付: {date}") from e


def slugify(title: str) -> str:
    """英字・数字以外を `-` にまとめ、前後の `-` を取る。英字が無ければ空を返す。"""
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s if re.search(r"[a-z0-9]", s) else ""


def cut(body: str, limit: int = MAX_BODY) -> str:
    """limit 文字以内にする。単語の切れ目（-）で切り、切れ目が無ければ強制的に切る。"""
    if len(body) <= limit:
        return body
    head = body[:limit + 1]
    k = head.rfind("-")
    cut_at = k if k > 0 else limit
    return body[:cut_at].rstrip("-")


def valid_name(name: str) -> bool:
    return bool(NAME_RE.match(name)) and len(name.split("_", 1)[1]) <= MAX_BODY


def make_candidates(date: str, titles, existing, count: int = COUNT, resume=()):
    """候補を count 個返す。existing は既にあるフォルダ名（YYMMDD_ 付きの全名）の集合。

    resume は、同じ入力の続きになる既存のフォルダ名。形（D13）に合うものだけを、避けずに先頭へ置く。
    """
    check_date(date)
    taken = set(existing)
    out = []
    seen = set()
    for name in resume:
        if len(out) < count and valid_name(name) and name not in out:
            out.append(name)
            taken.add(name)
            seen.add(name.split("_", 1)[1])

    def add(raw: str) -> None:
        body = cut(slugify(raw))
        if not body or body in seen:  # 空の題・同じ候補は捨てる（D15 の重複を除く）
            return
        seen.add(body)
        n = 1
        cand = body
        while f"{date}_{cand}" in taken:  # 既にあるフォルダとの衝突は -2・-3 で避ける（D18）
            n += 1
            suffix = f"-{n}"
            cand = cut(body, MAX_BODY - len(suffix)) + suffix
        taken.add(f"{date}_{cand}")
        out.append(f"{date}_{cand}")

    for t in titles:
        if len(out) >= count:
            break
        add(t)
    # 候補が足りないときは、既定の名前（source・source-2・…）で埋める（形を保つため）。
    # 既定の名前は重複で捨てられないよう、番号を付けて直接作る
    k = 1
    while len(out) < count:
        k += 1
        add(FALLBACK if k == 2 else f"{FALLBACK} {k}")
    return out[:count]


def existing_names(folder: Path):
    if not folder.is_dir():
        return []
    return [p.name for p in folder.iterdir()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", required=True, help="YYMMDD")
    ap.add_argument("--title", action="append", default=[], help="英訳・要約の候補（複数回指定）")
    ap.add_argument("--existing", type=Path, help="この中にある名前を避ける")
    ap.add_argument("--resume", action="append", default=[], metavar="NAME",
                    help="同じ入力の続きになる既存のフォルダ名（先頭の候補にする。複数回指定）")
    a = ap.parse_args()
    try:
        names = make_candidates(a.date, a.title, existing_names(a.existing) if a.existing else [],
                                resume=a.resume)
    except ValueError as e:
        print(f"ced_name: {e}", file=sys.stderr)
        return 2
    print(json.dumps(names, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
