#!/usr/bin/env python3
"""assemble.py — out/ の中間生成物を、作業フォルダの最終ファイルに転記する。標準ライブラリのみ。

すること（references/output-formats.md の転記表）:
  - 02_explanation_memo.md・11_question_and_answer.md・12_LLM_prompts_as_guide.md を、ひな形と out/ から作る
  - README.md の「## 生成AIの総括」の本文を out/06_summary.md で置き換える
  - 活用案の各案の末尾に、実測の字数「（N字）」を書く
  - 既にあるファイルの「スキルが作っていない節」（利用者が足した `##` の節）を保つ。
    その節のハッシュを out/00_manifest.json の foreign_sections に記録する
  - 2 回実行しても結果は同じ（差分が出ない。内容が同じファイルは書き直さない）

しないこと: 文章の書き換え・要約。out/ の内容はそのまま写す（見出しの段下げ・番号の振り直しだけ）。
01_source.md は変えない。検査は check_docs.py の仕事。

使い方:
  python3 assemble.py <作業フォルダ> [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from _common import (StopReason, char_count, contract_epilog, fence_flags, fill_template,
                     meta_bullets, normalize_body, normalize_text, read_text, run_main,
                     section_text, sha256_text)
from check_docs import (FINAL_FILES, MANIFEST, PROMPT_H2, README_H2, Sec, find, header_bullets,
                        inside, sec_body, sections_of)

TEMPLATES = Path(__file__).resolve().parent.parent / "assets" / "templates"
SEP = "-----\n[toTop](#totoppage)\n"
INTRO = "下のプロンプトを、生成AIのシステムプロンプト（カスタム指示）に貼り付けると、この資料の内容に沿ってガイドしてくれます。"
OUT_FILES = ["02_overview.md", "03_deep-questions.md", "04_grouping.md", "06_summary.md",
             "07_reflection.md", "08_faq.md", "10_system-prompt.md", "11_sample-questions.md"]


# ---- 読み取りの部品 ----------------------------------------------------------------
def strip_meta(text: str) -> str:
    """out/ のファイルの先頭のメタ情報（# 題・> 資料: …・---）を除いた本文。"""
    lines = normalize_text(text).split("\n")
    for i, ln in enumerate(lines[:14]):
        if ln.strip() == "---":
            return "\n".join(lines[i + 1:]).strip("\n")
    return "\n".join(l for j, l in enumerate(lines) if not (j == 0 and l.startswith("# "))).strip("\n")


def meta_value(text: str, key: str) -> str | None:
    m = re.search(rf"^> {re.escape(key)}:\s*(.+?)\s*$", normalize_text(text), re.M)
    return m.group(1) if m else None


def demote(text: str) -> str:
    """見出しを 1 段下げる（コードブロックの中は触らない）。"""
    lines = text.split("\n")
    flags = fence_flags(lines)
    return "\n".join("#" + ln if (not flags[i] and re.match(r"^#{1,5} ", ln)) else ln for i, ln in enumerate(lines))


class Problems:
    def __init__(self):
        self.items: list[str] = []

    def add(self, msg):
        self.items.append(msg)

    def raise_if_any(self):
        if self.items:
            shown = " / ".join(self.items[:6]) + (f" …ほか {len(self.items) - 6} 件" if len(self.items) > 6 else "")
            raise StopReason("MISSING_OUT_FILE", "転記に要る out/ の内容が足りません: " + shown)


def read_out(folder: Path, name: str, problems: Problems) -> str | None:
    p = folder / "out" / name
    if not p.is_file():
        problems.add(f"out/{name} が無い")
        return None
    return read_text(str(p))


# ---- 各ファイルの組み立て ------------------------------------------------------------
def parse_grouping(text: str, problems: Problems) -> list[str]:
    names = []
    for ln in normalize_text(text).split("\n"):
        m = re.match(r"^## グループ(\d+)：(.+?)\s*$", ln)
        if m:
            if int(m.group(1)) != len(names) + 1:
                problems.add(f"out/04_grouping.md のグループ番号が連番でない（{m.group(1)}）")
            names.append(m.group(2))
    if not names:
        problems.add("out/04_grouping.md に `## グループN：<名前>` が無い")
    if len(set(names)) != len(names):
        problems.add("out/04_grouping.md のグループ名が重複している")
    return names


def build_overview(o2: str, o3: str, problems: Problems) -> str:
    secs, lines = sections_of(strip_meta(o2))
    want = ["1. 要約", "2. 例え話", "3. セクション別の解説", "4. ユースケース", "5. 理解を深める質問"]
    bodies = {}
    for t in want:
        hit = find(secs, 2, t)
        if not hit:
            problems.add(f"out/02_overview.md に `## {t}` が無い")
        else:
            bodies[t] = sec_body(lines, hit[0])
    qs = []
    if "5. 理解を深める質問" in bodies:
        cur = None
        for ln in bodies["5. 理解を深める質問"].split("\n"):
            m = re.match(r"^\s*(\d+)\.\s+(.*\S)\s*$", ln)
            if m:
                qs.append(m.group(2))
                cur = len(qs) - 1
            elif ln.strip() and cur is not None:
                qs[cur] += " " + ln.strip()
        if len(qs) != 5:
            problems.add(f"out/02_overview.md の「5. 理解を深める質問」が {len(qs)} 問（5 問が必要）")
    s3, l3 = sections_of(strip_meta(o3))
    ans = [s for s in s3 if s.level == 3]
    if len(ans) != 5:
        problems.add(f"out/03_deep-questions.md の `###` が {len(ans)} 個（5 個が必要）")
    if problems.items:
        return ""
    parts = []
    for t in want[:4]:
        parts.append(f"### {t}\n{demote(bodies[t])}")
    blocks = []
    for i, (q, a) in enumerate(zip(qs, ans), 1):
        blocks.append(f"#### 質問{i}：{q}\n- **要点**：{a.title}\n{sec_body(l3, a)}")
    parts.append("### 5. 理解を深める質問\n" + "\n\n".join(blocks))
    return "\n\n".join(parts)


def build_themes(folder: Path, groups: list[str], problems: Problems) -> str:
    blocks = []
    for n, name in enumerate(groups, 1):
        t = read_out(folder, f"05_group-analysis-{n}.md", problems)
        if t is None:
            continue
        secs, lines = sections_of(strip_meta(t))
        hit = [s for s in secs if s.level == 2 and s.title.startswith("テーマ：")]
        if not hit:
            problems.add(f"out/05_group-analysis-{n}.md に `## テーマ：<グループ名>` が無い")
            continue
        if hit[0].title != f"テーマ：{name}":
            problems.add(f"out/05_group-analysis-{n}.md のテーマ名（{hit[0].title}）が 04 のグループ名（{name}）と違う")
            continue
        blocks.append(f"{SEP}## {hit[0].title}\n{sec_body(lines, hit[0])}\n")
    return "\n".join(blocks)


def build_reflection(o7: str, problems: Problems) -> str:
    secs, lines = sections_of(strip_meta(o7))
    cases = [s for s in secs if s.level == 3 and re.match(r"^案[1-3]", s.title)]
    if [s.title[:2] for s in cases] != ["案1", "案2", "案3"]:
        problems.add("out/07_reflection.md に `### 案1：…`・`### 案2：…`・`### 案3：…` が順に必要")
        return ""
    out = []
    for s in cases:
        body = re.sub(r"（\s*\d+\s*字）\s*$", "", sec_body(lines, s).rstrip())
        out.append(f"### {s.title}\n{body}（{char_count(body)}字）")
    return "\n\n".join(out)


def build_faq(o8: str, groups: list[str], problems: Problems) -> str:
    secs, lines = sections_of(strip_meta(o8))
    gs = [s for s in secs if s.level == 2 and re.match(r"^グループ\d+：", s.title)]
    names = [re.sub(r"^グループ\d+：", "", s.title).strip() for s in gs]
    if names != groups:
        problems.add(f"out/08_faq.md のグループ名（{names}）が 04 のグループ名（{groups}）と同じでない")
        return ""
    n = 0
    blocks = []
    for i, g in enumerate(gs, 1):
        items = []
        for q in inside(secs, g, 3):
            n += 1
            title = re.sub(r"^\d+\.\s*", "", q.title)
            items.append(f"### {n}. {title}\n{sec_body(lines, q)}")
        if not items:
            problems.add(f"out/08_faq.md の「{g.title}」に FAQ（`###`）が無い")
        blocks.append(f"{SEP}## FAQ｜グループ{i}：{names[i - 1]}\n" + "\n\n".join(items) + "\n")
    return "\n".join(blocks)


def build_prompt_file(tmpl: str, o10: str, o11: str, bullets: str, title: str) -> str:
    prompt = strip_meta(o10).strip("\n")
    model = meta_value(o10, "モデル") or "（記録なし）"
    t = fill_template(tmpl, {"title": title, "meta_bullets": bullets, "system_prompt_intro": INTRO,
                             "model": model, "sample_questions": strip_meta(o11).strip("\n")})
    fence = "```" if "```" not in prompt else "~~~~"
    t = t.replace("```\n{{system_prompt}}\n```", f"{fence}\n{{{{system_prompt}}}}\n{fence}")
    return fill_template(t, {"system_prompt": prompt})


# ---- スキルが作っていない節の保全 -----------------------------------------------------
def is_known(file: str, title: str) -> bool:
    if file == "README.md":
        return title in README_H2
    if file == "02_explanation_memo.md":
        return title in ("解説", "活用案") or title.startswith("テーマ：")
    if file == "11_question_and_answer.md":
        return title.startswith("FAQ｜グループ")
    if file == "12_LLM_prompts_as_guide.md":
        return title in PROMPT_H2
    return True


def foreign_sections(file: str, text: str) -> list[dict]:
    """スキルが作っていない `##` の節を [{heading, after, text}] で返す（after は直前の既知の節の題）。"""
    secs, _ = sections_of(text)
    out, prev = [], None
    for s in secs:
        if s.level != 2:
            continue
        if is_known(file, s.title):
            prev = s.title
        else:
            out.append({"heading": s.title, "after": prev, "text": section_text(text, s.title, 2)})
    return out


def reinsert(new_text: str, foreign: list[dict]) -> str:
    """新しく作ったテキストに、既存の「スキルが作っていない節」を元の位置（直前の既知の節の後ろ）に戻す。"""
    for fs in foreign:
        lines = new_text.split("\n")
        secs, _ = sections_of(new_text)
        at = None
        if fs["after"] is not None:
            hit = [s for s in secs if s.level == 2 and s.title == fs["after"]]
            if hit:
                at = hit[0]
        if at is None:  # 直前の節が無い・先頭だった → 最後の `##` の節の後ろ
            tops = [s for s in secs if s.level == 2]
            at = tops[-1] if tops else None
        if at is None:
            continue
        end = at.end - 1  # 次の見出しの行（0 から）
        while end > at.line and lines[end - 1].strip() in ("", "-----", "[toTop](#totoppage)"):
            end -= 1
        # 末尾の節のときは、ファイルの最後の区切りの手前に入れる
        ins = ["", "-----", "[toTop](#totoppage)"] + fs["text"].rstrip("\n").split("\n")
        lines[end:end] = ins
        new_text = "\n".join(lines)
    return new_text


def replace_section_body(text: str, title: str, new_body: str) -> str:
    lines = text.split("\n")
    secs, _ = sections_of(text)
    hit = [s for s in secs if s.level == 2 and s.title == title]
    if not hit:
        raise StopReason("MISSING_OUT_FILE", f"README.md に `## {title}` が無い", "README.md を scaffold.py で作り直す前に、骨格を確かめてください。")
    s = hit[0]
    end = s.end - 1
    while end > s.line and lines[end - 1].strip() in ("", "-----", "[toTop](#totoppage)"):
        end -= 1
    return "\n".join(lines[:s.line] + new_body.split("\n") + lines[end:])


# ---- 本体 --------------------------------------------------------------------------
def assemble(folder: Path, dry_run: bool) -> dict:
    if not folder.is_dir():
        raise StopReason("NO_INPUT", f"作業フォルダが見つかりません: {folder}")
    readme_p = folder / "README.md"
    if not readme_p.is_file():
        raise StopReason("NO_INPUT", f"README.md が無い（scaffold.py で作った作業フォルダを渡してください）: {folder}",
                         "先に取り込み（scaffold.py）を行ってください。")
    problems = Problems()
    outs = {n: read_out(folder, n, problems) for n in OUT_FILES}
    groups = parse_grouping(outs["04_grouping.md"], problems) if outs["04_grouping.md"] else []
    problems.raise_if_any()

    readme = read_text(str(readme_p))
    hb = header_bullets(readme)
    title = hb.get("title", "")
    if not title:
        raise StopReason("NO_INPUT", "README.md の題名の下に `title` が無い", "scaffold.py の骨格を確かめてください。")
    bullets = meta_bullets([("title", title), ("url", hb.get("url") or None)])

    overview = build_overview(outs["02_overview.md"], outs["03_deep-questions.md"], problems)
    themes = build_themes(folder, groups, problems)
    reflection = build_reflection(outs["07_reflection.md"], problems)
    faq = build_faq(outs["08_faq.md"], groups, problems)
    problems.raise_if_any()

    t = lambda n: (TEMPLATES / n).read_text(encoding="utf-8")
    new = {
        "02_explanation_memo.md": fill_template(t("02_explanation_memo.md"), {
            "title": title, "meta_bullets": bullets, "overview_block": overview,
            "theme_blocks": themes, "reflection_block": reflection}),
        "11_question_and_answer.md": fill_template(t("11_question_and_answer.md"), {
            "title": title, "meta_bullets": bullets, "faq_blocks": faq}),
        "12_LLM_prompts_as_guide.md": build_prompt_file(
            t("12_LLM_prompts_as_guide.md"), outs["10_system-prompt.md"], outs["11_sample-questions.md"], bullets, title),
        "README.md": replace_section_body(readme, "生成AIの総括", strip_meta(outs["06_summary.md"]).strip("\n")),
    }
    # スキルが作っていない節を保つ（README は元のファイルを書き換えるだけなので、そのまま残る）
    kept = {}
    for name in ("02_explanation_memo.md", "11_question_and_answer.md", "12_LLM_prompts_as_guide.md"):
        p = folder / name
        if p.is_file():
            fs = foreign_sections(name, read_text(str(p)))
            if fs:
                new[name] = reinsert(new[name], fs)
    for name in FINAL_FILES:
        txt = new.get(name) or (read_text(str(folder / name)) if (folder / name).is_file() else None)
        if txt is not None and name != "01_source.md":
            for fs in foreign_sections(name, txt):
                kept.setdefault(name, []).append({
                    "file": name, "heading": fs["heading"], "level": 2,
                    "sha256": sha256_text(normalize_body(fs["text"]))})

    written, unchanged = [], []
    for name, text in new.items():
        text = normalize_text(text)
        if not text.endswith("\n"):
            text += "\n"
        p = folder / name
        if p.is_file() and read_text(str(p)) == text:
            unchanged.append(name)
            continue
        written.append(name)
        if not dry_run:
            p.write_text(text, encoding="utf-8", newline="\n")
    # manifest の foreign_sections を更新する（無ければ警告だけ）
    warnings = []
    mp = folder / MANIFEST
    flat = [fs for lst in kept.values() for fs in lst]
    if mp.is_file():
        try:
            m = json.loads(mp.read_text(encoding="utf-8"))
        except ValueError:
            m = None
            warnings.append(f"{MANIFEST} を読めないため、foreign_sections を記録しなかった")
        if m is not None and m.get("foreign_sections", []) != flat:
            m["foreign_sections"] = flat
            if not dry_run:
                mp.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            written.append(MANIFEST)
    else:
        warnings.append(f"{MANIFEST} が無いため、foreign_sections を記録しなかった")
    if "（記録なし）" in new["12_LLM_prompts_as_guide.md"]:
        warnings.append("out/10_system-prompt.md に `> モデル:` が無い（モデル名は「（記録なし）」と書いた）")
    return {"folder": str(folder), "dry_run": dry_run, "written": written, "unchanged": unchanged,
            "groups": groups, "foreign_sections": [f"{f['file']}: {f['heading']}" for f in flat],
            "warnings": warnings}


def main() -> None:
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "out/ の中間生成物を、作業フォルダの最終ファイルに転記する。文章は書き換えない。\n"
            "\n"
            "入力:\n"
            "  <folder>  scaffold.py で作った作業フォルダ（README.md・01_source.md があり、out/ に\n"
            "            02・03・04・05-N・06・07・08・10・11 がある）\n"
            "作るもの・更新するもの:\n"
            "  02_explanation_memo.md・11_question_and_answer.md・12_LLM_prompts_as_guide.md\n"
            "  README.md の「## 生成AIの総括」の本文／out/00_manifest.json の foreign_sections\n"
            "  2 回実行しても同じ結果（内容が同じファイルは書き直さない）。01_source.md は変えない。\n"
            "  利用者が足した `##` の節（スキルが作っていない節）は、そのまま保つ。"),
        epilog=contract_epilog(
            ("NO_INPUT", "MISSING_OUT_FILE"),
            "結果の JSON（written・unchanged・groups・foreign_sections・warnings）"))
    ap.add_argument("folder", help="作業フォルダ")
    ap.add_argument("--dry-run", action="store_true", help="何も書かずに、書く予定のファイルだけを JSON で返す")
    args = ap.parse_args()
    result = assemble(Path(args.folder), args.dry_run)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    run_main(main)
