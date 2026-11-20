#!/usr/bin/env python3
"""scaffold.py — 入力の Markdown から、作業フォルダの骨格を作る。標準ライブラリのみ。

すること:
  - frontmatter を読む（無い・欠けていても止まらない。警告を出して続ける）
  - プロファイル（video / article / document）を決める
  - 作業フォルダを作り、01_source.md に入力の本文を複製する（本文は一字も変えない）、
    README.md の骨格、out/00_manifest.json、out/00_run-report.md を置く
  - セクションの候補（見出し・チャプター）と、そのまま貼れる目次の行を JSON で返す

しないこと（LLM の仕事）: 要約・セクション分け・README の概要。ひな形の `{{…}}` のまま残す。
入力の Markdown は書き換えない。作業フォルダが既にあれば何も書かずに止まる（DEST_EXISTS。ただし中身が .work/ だけなら、まだ空とみなす）。

使い方:
  python3 scaffold.py <入力.md> [--dest DIR] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from _common import (SKILL_VERSION, SOURCE_BODY_MARKER, StopReason, char_count, contract_epilog,
                     fill_template, meta_bullets, normalize_body, normalize_text, parse_frontmatter, parse_headings,
                     read_text, run_main, sha256_file, sha256_text, slugify, split_source)

TEMPLATES = Path(__file__).resolve().parent.parent / "assets" / "templates"
MIN_BODY_CHARS = 30  # これより短い本文は EMPTY_CONTENT
MAX_SECTIONS = 12    # 見出しがこれより多いときは、上位の見出しでまとめる（目安）

FORMAT_TO_PROFILE = {"youtube": "video", "html": "article",
                     "pdf": "document", "docx": "document", "pptx": "document", "xlsx": "document",
                     # v0.0.2：collect_sources.py が包んだ入力（文字・コード・字幕）
                     "text": "article", "code": "article", "subtitle": "video"}

_STAMP = re.compile(r"^\*\*\[(\d{1,2}(?::\d{2}){1,2})\]\*\*", re.M)
_CHAPTER = re.compile(r"^(\d{1,2}(?::\d{2}){1,2})[ \t]+(\S.*)$")
_DOC_MARK = re.compile(r"<!--\s*(?:Slide number:|page)\s*\d+\s*-->", re.I)


# ---- プロファイルの判定 --------------------------------------------------------------
def decide_profile(fm: dict, body: str) -> tuple[str, str]:
    """(プロファイル, 判定の理由)。frontmatter の source_format を優先し、無ければ本文から推定する。"""
    fmt = fm.get("source_format")
    if fmt in FORMAT_TO_PROFILE:
        return FORMAT_TO_PROFILE[fmt], f"frontmatter の source_format が {fmt}"
    if len(_STAMP.findall(body)) >= 3:
        return "video", "段落頭に **[MM:SS]** が 3 つ以上ある（frontmatter なし）"
    if len(_DOC_MARK.findall(body)) >= 2:
        return "document", "ページ・スライド番号の区切りが 2 つ以上ある（frontmatter なし）"
    return "article", "上のどれにも当たらない（frontmatter なし。見出しと段落の文書とみなす）"


def norm_ts(ts: str) -> str:
    """`0:40` → `00:40`、`1:02:03` → `1:02:03`（時間があるときはそのまま）。"""
    parts = ts.split(":")
    if len(parts) == 2:
        return f"{int(parts[0]):02d}:{parts[1]}"
    return f"{int(parts[0])}:{parts[1]}:{parts[2]}"


# ---- セクションの候補 ------------------------------------------------------------------
def video_chapters(fm: dict, body: str) -> list[dict]:
    """概要欄のチャプター（`0:00 名前` の行。字幕より前の部分）を読み、範囲つきで返す。"""
    head = body.split("## Transcript", 1)[0]
    raw = []
    for ln in head.split("\n"):
        m = _CHAPTER.match(ln.strip())
        if m:
            raw.append((norm_ts(m.group(1)), m.group(2).strip()))
    if len(raw) < 2 or raw[0][0] not in ("00:00", "0:00:00"):
        return []  # チャプターとみなせない（YouTube は 0:00 から始まる 3 つ以上が条件だが、ここでは 2 つ以上）
    stamps = _STAMP.findall(body)
    end_last = norm_ts(fm["duration"]) if fm.get("duration") else (norm_ts(stamps[-1]) if stamps else "")
    out = []
    for i, (start, name) in enumerate(raw):
        end = raw[i + 1][0] if i + 1 < len(raw) else end_last
        out.append({"number": i + 1, "name": name, "start": start, "end": end})
    return out


def heading_candidates(full_text: str, marker_line: int | None) -> list[dict]:
    """01_source.md の本文の見出しを、アンカーつきで返す（本文の最初の `#` の題名は除く）。"""
    seen: dict[str, int] = {}
    out = []
    first_body_heading = True
    for ln, lv, title in parse_headings(full_text):
        base = slugify(title)
        n = seen.get(base, 0)
        anchor = base if n == 0 else f"{base}-{n}"
        seen[base] = n + 1
        if marker_line is None or ln <= marker_line:
            continue  # 冒頭（複製の前）の見出しは数えるだけ
        if first_body_heading:
            first_body_heading = False
            if lv == 1:
                continue  # 本文の最初の `# ` は文書の題名（セクションにしない）
        out.append({"line": ln, "level": lv, "title": title, "anchor": anchor})
    return out


def suggest_sections(cands: list[dict]) -> tuple[list[dict], str]:
    """見出しの候補から、目次にする見出しを選ぶ。(選んだ見出し, 説明)。"""
    if not cands:
        return [], "本文に見出しが無い"
    top = min(c["level"] for c in cands)
    chosen = [c for c in cands if c["level"] == top]
    note = f"レベル {top} の見出し {len(chosen)} 件"
    if len(chosen) > MAX_SECTIONS:
        note += f"（目安の {MAX_SECTIONS} 件を超えている。上位の見出しでまとめることを検討する）"
    return chosen, note


# ---- 作業フォルダの名前 ---------------------------------------------------------------
# 既定は、今いるフォルダの直下の YYMMDD_<名前>/（explain の形と同じ。V3-M2）。
# 名前の決まりは ced-url-to-md の ced_name.py と同じ（他のスキルのファイルは import しないため、ここに持つ。
# 同じ結果になることは tests/test_name_parity.py で確かめる）。
NAME_MAX = 40
NAME_FALLBACK = "source"


def default_name(stem: str) -> str:
    """英小文字・数字・-（それ以外は - にまとめる）、40 文字以内（単語の切れ目で切る）。英字が無ければ source。"""
    body = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    if not re.search(r"[a-z0-9]", body):
        return NAME_FALLBACK
    if len(body) > NAME_MAX:
        k = body[:NAME_MAX + 1].rfind("-")
        body = body[:k if k > 0 else NAME_MAX].rstrip("-")
    return body


def default_dest(input_path: Path, today=None) -> Path:
    """既定の作業フォルダ: <今いるフォルダ>/YYMMDD_<名前>/（日付は実行した日）。"""
    day = today or datetime.now()
    return Path.cwd() / f"{day:%y%m%d}_{default_name(input_path.stem)}"


# ---- 本体 ---------------------------------------------------------------------------
STEP_FILES = [  # (Step, out/ のファイル名)。05 はグループの数だけ。
    ("1", "02_overview.md"), ("2", "03_deep-questions.md"), ("3", "04_grouping.md"),
    ("4", "05_group-analysis-<N>.md"), ("5", "06_summary.md"), ("6", "07_reflection.md"),
    ("7", "08_faq.md"), ("8-A", "09_input-memo.md"), ("8-B", "10_system-prompt.md"),
    ("9", "11_sample-questions.md")]


def steps_status(d: Path) -> tuple[dict, list[str], list[str]]:
    """out/ の中間生成物の有無。(Step ごとの状態, 足りない Step, グループ名)。何も書かない。"""
    out = d / "out"
    groups: list[str] = []
    p4 = out / "04_grouping.md"
    if p4.is_file():
        for ln in normalize_text(read_text(str(p4))).split("\n"):
            m = re.match(r"^## グループ(\d+)：(.+?)\s*$", ln)
            if m:
                groups.append(m.group(2))
    status: dict = {}
    for step, name in STEP_FILES:
        if "<N>" in name:
            files = [name.replace("<N>", str(n)) for n in range(1, len(groups) + 1)]
            status[step] = bool(files) and all((out / f).is_file() for f in files)
        else:
            status[step] = (out / name).is_file()
    return status, [s for s, ok in status.items() if not ok], groups


def input_state(d: Path) -> dict:
    """manifest に控えた入力が、いまも同じか（入力が後から変わっていないか）。"""
    mf = d / "out" / "00_manifest.json"
    if not mf.is_file():
        return {"input_changed": None, "input_path": None,
                "input_note": "out/00_manifest.json が無いので、入力が変わったかは分からない"}
    try:
        m = json.loads(read_text(str(mf)))
        path, sha = m["input"]["path"], m["input"]["sha256"]
    except (ValueError, KeyError, TypeError):
        return {"input_changed": None, "input_path": None,
                "input_note": "out/00_manifest.json を読めないので、入力が変わったかは分からない"}
    if not Path(path).is_file():
        return {"input_changed": None, "input_path": path, "input_note": "控えた入力のファイルが今は見つからない"}
    changed = sha256_file(path) != sha
    return {"input_changed": changed, "input_path": path,
            "input_note": ("入力が作業フォルダを作った後に変わっている。01_source.md は古い複製のまま。"
                           "新しい入力で作り直すなら別名の作業フォルダに（Q6）" if changed
                           else "入力は作業フォルダを作ったときと同じ")}


def existing_folder_report(d: Path) -> dict:
    """README.md と 01_source.md が既にあるフォルダ。使うだけで、何も書かない。"""
    src = d / "01_source.md"
    text = read_text(str(src))
    head, body, mark = split_source(text)
    status, missing, groups = steps_status(d)
    return {
        "mode": "existing_folder",
        "dest": str(d),
        "files": {n: (d / n).is_file() for n in (
            "README.md", "01_source.md", "02_explanation_memo.md",
            "11_question_and_answer.md", "12_LLM_prompts_as_guide.md", "out/00_manifest.json")},
        "source_has_body_marker": mark is not None,
        "source_has_summary": "> 要約：" in head,
        "source_has_toc": re.search(r"^## セクション目次\s*$", head, re.M) is not None,
        "steps": status,
        "missing_steps": missing,
        "groups": groups,
        **input_state(d),
        "note": ("作り直さない。01_source.md の冒頭が足りなければ足す。スキルが作っていない節は変えない。"
                 "out/ にあるファイルは、指示が無い限り作り直さない（足りない Step だけ作る）。"),
    }


def build(input_path: Path, dest: Path, dry_run: bool) -> dict:
    raw_text = read_text(str(input_path))
    fm, body_raw, warns = parse_frontmatter(raw_text)
    body = normalize_body(body_raw)
    if len(body.strip()) < MIN_BODY_CHARS:
        raise StopReason("EMPTY_CONTENT", f"本文が空、または短すぎます（{len(body.strip())} 字）: {input_path}")
    # explain は、先に collect_sources.py prepare が <出力先>/.work/ を作る。.work/ だけのフォルダは「まだ空」とみなす
    if dest.exists() and any(e.name != ".work" for e in dest.iterdir()):
        raise StopReason("DEST_EXISTS", f"作業フォルダが既にあります（何も書きません）: {dest}")
    for w in warns:
        print(f"[warn] {w}", file=sys.stderr)

    profile, profile_reason = decide_profile(fm, body)
    title = fm.get("title") or ""
    if not title:
        heads = [t for _, lv, t in parse_headings(body) if lv == 1]
        title = heads[0] if heads else input_path.stem
        warns.append(f"title を本文から決めた: {title}")
    url = fm.get("source_url") if re.match(r"^https?://", fm.get("source_url", "")) else None

    source_bullets = meta_bullets([
        ("title", title), ("url", url), ("source_format", fm.get("source_format") or None),
        ("retrieved_at", fm.get("retrieved_at") or None),
        ("channel", fm.get("channel") or None), ("published", fm.get("published") or None),
        ("duration", fm.get("duration") or None)])
    readme_bullets = meta_bullets([
        ("title", title), ("url", url), ("source_format", fm.get("source_format") or None),
        ("retrieved_at", fm.get("retrieved_at") or None), ("profile", profile),
        ("content_type", "{{content_type}}"),
        ("channel", fm.get("channel") or None), ("published", fm.get("published") or None),
        ("duration", fm.get("duration") or None)])

    tmpl_src = (TEMPLATES / "01_source.md").read_text(encoding="utf-8")
    head_part = tmpl_src.split("{{body}}")[0]
    source_text = fill_template(head_part, {"title": title, "meta_bullets": source_bullets}) + body
    readme_text = fill_template((TEMPLATES / "README.md").read_text(encoding="utf-8"),
                                {"title": title, "meta_bullets": readme_bullets})

    # セクションの候補（01_source.md の実際の行番号でアンカーを決める）
    _, _, marker_line = split_source(source_text)
    cands = heading_candidates(source_text, marker_line)
    chosen, chosen_note = suggest_sections(cands)
    chapters = video_chapters(fm, body) if profile == "video" else []
    if profile == "video":
        # 動画の本文の見出し（概要・Transcript）はセクションではない。チャプターが無ければスキルが区切る
        chosen, chosen_note = [], "チャプターなし（スキルが話題の切れ目で区切る）"
    toc_source, toc_readme = [], []
    if chapters:
        for c in chapters:
            line = f"- {c['number']} : {c['name']} ｜ {c['start']}〜{c['end']}"
            toc_source.append(line)
            toc_readme.append(line)
    else:
        for i, c in enumerate(chosen, 1):
            toc_source.append(f"- {i} : [{c['title']}](#{c['anchor']})")
            toc_readme.append(f"- {i} : [{c['title']}](./01_source.md#{c['anchor']})")

    created = datetime.now().astimezone().isoformat(timespec="seconds")
    manifest = {
        "schema": 1, "skill_version": SKILL_VERSION, "created_at": created,
        "input": {"path": str(input_path.resolve()), "sha256": sha256_file(str(input_path)),
                  "bytes": input_path.stat().st_size},
        "body_sha256": sha256_text(body), "profile": profile,
        "frontmatter": fm, "foreign_sections": [],
    }
    report = (
        "# 実行記録\n\n"
        f"> 資料: {title}\n> ステップ: 取り込み（scaffold.py）\n> 生成日: {created[:10]}\n\n---\n\n"
        "## 入力\n"
        f"- 入力: `{input_path}`\n"
        f"- frontmatter: {'あり（' + '・'.join(fm) + '）' if fm else 'なし'}"
        + ("" if not warns else "\n- 警告: " + " / ".join(warns)) + "\n"
        f"- プロファイル: {profile}（{profile_reason}）\n"
        "- 内容の種類: （Step 0 で決める）\n\n"
        "## 取り込み\n"
        f"- 本文: {char_count(body, markdown=False)} 字（複製。ハッシュは 00_manifest.json）\n"
        f"- セクションの候補: {'概要欄のチャプター ' + str(len(chapters)) + ' 件' if chapters else chosen_note}\n"
    )

    files = ["README.md", "01_source.md", "out/00_manifest.json", "out/00_run-report.md"]
    if not dry_run:
        (dest / "out").mkdir(parents=True, exist_ok=True)
        (dest / "README.md").write_text(readme_text, encoding="utf-8", newline="\n")
        (dest / "01_source.md").write_text(source_text, encoding="utf-8", newline="\n")
        (dest / "out" / "00_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        (dest / "out" / "00_run-report.md").write_text(report, encoding="utf-8", newline="\n")

    return {
        "mode": "created", "dry_run": dry_run, "dest": str(dest), "files": files,
        "input": str(input_path.resolve()), "profile": profile, "profile_reason": profile_reason,
        "title": title, "url": url, "frontmatter": fm, "frontmatter_warnings": warns,
        "body_chars": char_count(body, markdown=False), "body_sha256": manifest["body_sha256"],
        "summary_draft": (fm.get("summary") or "")[:200],
        "sections": {
            "source": "chapters" if chapters else ("headings" if chosen else "none"),
            "note": chosen_note if not chapters else f"概要欄のチャプター {len(chapters)} 件",
            "chapters": chapters, "headings": cands,
            "toc_for_source": toc_source, "toc_for_readme": toc_readme,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "入力の Markdown から、作業フォルダの骨格を作る。入力は書き換えない。\n"
            "\n"
            "入力:\n"
            "  <input>      url-to-md が作った Markdown（1 つ）。frontmatter が無くても止まらない。\n"
            "               README.md と 01_source.md が既にあるフォルダを渡すと、何も書かずに状態だけ返す。\n"
            "作るもの:\n"
            "  <dest>/README.md（骨格）・01_source.md（本文の複製＋冒頭）・\n"
            "  out/00_manifest.json（入力と本文のハッシュ）・out/00_run-report.md\n"
            "  要約・目次・概要・総括・content_type は {{…}} のまま残す（LLM が書く）。"),
        epilog=contract_epilog(
            ("NO_INPUT", "EMPTY_CONTENT", "MULTI_SOURCE", "DEST_EXISTS"),
            "結果の JSON（dest・profile・title・sections の候補と目次の行など）",
            notes=["--dest を省くと、今いるフォルダの直下に YYMMDD_<名前>/ を作る"
                   "（日付は実行した日。名前は入力のファイル名を、英小文字・数字・- の 40 文字以内にしたもの。"
                   "英字が無ければ source）。",
                   "作業フォルダが既にあるときは何も書かずに DEST_EXISTS で止まる（上書きしない）。"]))
    ap.add_argument("input", nargs="+", help="入力の Markdown（1 つ）")
    ap.add_argument("--dest", default=None, metavar="DIR",
                    help="作業フォルダ（省略時は、今いるフォルダの直下の YYMMDD_<名前>/）")
    ap.add_argument("--dry-run", action="store_true", help="何も書かずに、作る内容だけを JSON で返す")
    args = ap.parse_args()

    if len(args.input) > 1:
        raise StopReason("MULTI_SOURCE", f"入力が {len(args.input)} 個あります（v0.1.0 は 1 つだけ）")
    arg = args.input[0]
    if re.match(r"^https?://", arg):
        raise StopReason("NO_INPUT", f"URL は取得しません: {arg}",
                         "先に url-to-md で Markdown にしてから、そのパスを渡してください。")
    path = Path(arg)
    if path.is_dir():
        if (path / "README.md").is_file() and (path / "01_source.md").is_file():
            result = existing_folder_report(path)
            sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            return
        raise StopReason("NO_INPUT", f"Markdown のファイルではなくフォルダです: {arg}",
                         "Markdown のパスを渡してください（README.md と 01_source.md があるフォルダは使えます）。")
    if not path.is_file():
        raise StopReason("NO_INPUT", f"入力のファイルが見つかりません: {arg}")
    dest = Path(args.dest) if args.dest else default_dest(path)
    result = build(path, dest, args.dry_run)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if not args.dry_run:
        print(f"[ok] 作業フォルダを作りました: {dest}", file=sys.stderr)


if __name__ == "__main__":
    run_main(main)
