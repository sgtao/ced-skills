"""assemble.py のテスト：out/ → 最終ファイル。転記の一致・2 回実行で差分なし・節の保全・MISSING_OUT_FILE。"""
from __future__ import annotations

import json
import os
import re
import shutil

import pytest

from conftest import GOLDEN_VIDEO, INPUTS, edit, run_script
from check_docs import run_checks
from test_ingest import ingest
import _common as C

FINALS = ["02_explanation_memo.md", "11_question_and_answer.md", "12_LLM_prompts_as_guide.md"]


def failed_ids(folder):
    return [i["id"] for i in run_checks(str(folder))["items"] if i["status"] == "FAIL"]


def read(folder, name):
    return (folder / name).read_text(encoding="utf-8")


@pytest.fixture
def pre(tmp_path):
    """転記の前の作業フォルダ：README の総括が空（{{summary_block}}）で、02・11・12 が無い。out/ は見本のまま。"""
    d = tmp_path / "w"
    shutil.copytree(GOLDEN_VIDEO, d)
    for n in FINALS:
        (d / n).unlink()
    r = read(d, "README.md")
    a, b = r.index("## 生成AIの総括\n") + len("## 生成AIの総括\n"), r.index("-----\n[toTop](#totoppage)\n## 本文")
    (d / "README.md").write_text(r[:a] + "{{summary_block}}\n\n" + r[b:], encoding="utf-8")
    return d


def assemble(folder, *args):
    p = run_script("assemble.py", folder, *args)
    return p, (json.loads(p.stdout) if p.stdout.strip() else None)


def test_out_to_final_matches_golden_byte_for_byte(pre):
    p, r = assemble(pre)
    assert p.returncode == 0, p.stderr
    assert sorted(r["written"]) == sorted(FINALS + ["README.md"])
    for n in FINALS + ["README.md"]:
        assert read(pre, n) == read(GOLDEN_VIDEO, n), n
    assert r["groups"] == ["在庫回転率の考え方", "計算と実践"]
    assert failed_ids(pre) == []  # 全項目 PASS


def test_second_run_makes_no_diff_and_keeps_mtime(pre):
    assemble(pre)
    before = {n: read(pre, n) for n in FINALS + ["README.md"]}
    for n in before:
        os.utime(pre / n, (1_000_000_000, 1_000_000_000))
    p, r = assemble(pre)
    assert r["written"] == [] and sorted(r["unchanged"]) == sorted(before)
    for n, t in before.items():
        assert read(pre, n) == t
        assert int((pre / n).stat().st_mtime) == 1_000_000_000  # 書き直していない


def test_01_source_and_manifest_hash_untouched(pre):
    src = (pre / "01_source.md").read_bytes()
    m = json.loads(read(pre, "out/00_manifest.json"))
    assemble(pre)
    assert (pre / "01_source.md").read_bytes() == src
    assert json.loads(read(pre, "out/00_manifest.json")) == m  # foreign_sections が空のまま


def test_dry_run_writes_nothing(pre):
    p, r = assemble(pre, "--dry-run")
    assert p.returncode == 0 and r["dry_run"] is True and sorted(r["written"]) == sorted(FINALS + ["README.md"])
    assert not any((pre / n).exists() for n in FINALS)
    assert "{{summary_block}}" in read(pre, "README.md")


def test_reflection_counts_are_measured_not_written(pre):
    assemble(pre)
    memo = read(pre, "02_explanation_memo.md")
    counts = re.findall(r"（(\d+)字）", memo)
    assert len(counts) == 3
    for body, n in re.findall(r"### 案\d：[^\n]*\n(.+?)（(\d+)字）", memo):
        assert int(n) == C.char_count(body)
    # out/07 を書き換えると、字数も変わる。out/07 に（N字）が書いてあっても、実測で置き換える
    edit(pre, "out/07_reflection.md", "まずは1か月だけ試し、数字で見る手間が続けられるかを確かめる。", "まずは1か月だけ試す。（999字）")
    assemble(pre)
    memo2 = read(pre, "02_explanation_memo.md")
    assert "999字" not in memo2
    assert re.findall(r"（(\d+)字）", memo2)[0] != counts[0]
    assert failed_ids(pre) == []


def test_faq_numbers_are_renumbered_globally(pre):
    out8 = read(pre, "out/08_faq.md")
    assemble(pre)
    nums = re.findall(r"^### (\d+)\. ", read(pre, "11_question_and_answer.md"), re.M)
    assert nums == [str(i) for i in range(1, 8)]
    # out/08 では、グループ 2 が 1 から始まる仮の番号（転記で通し番号になる）
    g2 = out8.split("## グループ2：")[1]
    assert re.findall(r"^### (\d+)\. ", g2, re.M)[0] == "1"


def test_system_prompt_with_code_fence_uses_longer_fence(pre):
    edit(pre, "out/10_system-prompt.md", "# 役割", "# 役割\n```\n例\n```")
    p, _ = assemble(pre)
    assert p.returncode == 0
    t = read(pre, "12_LLM_prompts_as_guide.md")
    assert "~~~~\nあなたは" in t
    assert failed_ids(pre) == []  # コードブロックの中の見出し・フェンスで検査が崩れない


def test_missing_model_gives_warning(pre):
    edit(pre, "out/10_system-prompt.md", "> モデル: 手作りの見本（人が書いたもので、生成AIの出力ではありません）\n", "")
    p, r = assemble(pre)
    assert p.returncode == 0 and any("モデル" in w for w in r["warnings"])
    assert "生成したモデル：（記録なし）" in read(pre, "12_LLM_prompts_as_guide.md")


# ---- 足りないとき ----------------------------------------------------------------------
@pytest.mark.parametrize("missing", ["out/08_faq.md", "out/05_group-analysis-2.md", "out/10_system-prompt.md", "out/04_grouping.md"])
def test_missing_out_file_stops_and_writes_nothing(pre, missing):
    (pre / missing).unlink()
    p, _ = assemble(pre)
    assert p.returncode == 1
    last = p.stderr.strip().splitlines()
    assert last[-1] == "REASON=MISSING_OUT_FILE"
    assert missing in p.stderr
    assert not any((pre / n).exists() for n in FINALS)
    assert "{{summary_block}}" in read(pre, "README.md")  # README も触らない


def test_wrong_number_of_questions_or_answers(pre):
    t = read(pre, "out/02_overview.md")
    (pre / "out/02_overview.md").write_text(re.sub(r"(?m)^5\. .*\n", "", t), encoding="utf-8")
    p, _ = assemble(pre)
    assert p.returncode == 1 and "4 問" in p.stderr and p.stderr.strip().splitlines()[-1] == "REASON=MISSING_OUT_FILE"


def test_group_name_mismatch_between_out_files(pre):
    edit(pre, "out/08_faq.md", "## グループ2：計算と実践", "## グループ2：別の名前")
    p, _ = assemble(pre)
    assert p.returncode == 1 and "グループ名" in p.stderr
    edit(pre, "out/08_faq.md", "## グループ2：別の名前", "## グループ2：計算と実践")
    edit(pre, "out/05_group-analysis-1.md", "## テーマ：在庫回転率の考え方", "## テーマ：違う名前")
    p, _ = assemble(pre)
    assert p.returncode == 1 and "違う名前" in p.stderr


def test_no_readme_is_no_input(tmp_path):
    (tmp_path / "x").mkdir()
    p, _ = assemble(tmp_path / "x")
    assert p.returncode == 1 and p.stderr.strip().splitlines()[-1] == "REASON=NO_INPUT"
    p, _ = assemble(tmp_path / "nothing")
    assert p.stderr.strip().splitlines()[-1] == "REASON=NO_INPUT"


# ---- スキルが作っていない節の保全 ------------------------------------------------------
def add_user_sections(d):
    memo = read(d, "02_explanation_memo.md")
    memo = memo.replace("-----\n[toTop](#totoppage)\n## 活用案",
                        "-----\n[toTop](#totoppage)\n## 私のメモ\n- 自分の店では90日ではなく60日にする。\n\n-----\n[toTop](#totoppage)\n## 活用案")
    (d / "02_explanation_memo.md").write_text(memo, encoding="utf-8")
    rd = read(d, "README.md")
    rd = rd.replace("-----\n[toTop](#totoppage)\n## 本文", "-----\n[toTop](#totoppage)\n## 学習メモ\n- README の利用者の節\n\n-----\n[toTop](#totoppage)\n## 本文")
    (d / "README.md").write_text(rd, encoding="utf-8")
    faq = read(d, "11_question_and_answer.md")
    faq = faq.rstrip("\n").rsplit("-----\n[toTop](#totoppage)", 1)[0] + "-----\n[toTop](#totoppage)\n## 追加の質問\n- 利用者が足した節\n\n-----\n[toTop](#totoppage)\n"
    (d / "11_question_and_answer.md").write_text(faq, encoding="utf-8")


def test_foreign_sections_are_kept_in_place_and_recorded(pre):
    assemble(pre)
    add_user_sections(pre)
    memo_before, faq_before, rd_before = (read(pre, n) for n in ("02_explanation_memo.md", "11_question_and_answer.md", "README.md"))
    # out/ を変えて作り直しても、利用者の節は残る
    edit(pre, "out/06_summary.md", "在庫は「回った回数」で見る", "在庫は回転で見る")
    p, r = assemble(pre)
    assert p.returncode == 0, p.stderr
    assert sorted(r["foreign_sections"]) == sorted(["02_explanation_memo.md: 私のメモ", "11_question_and_answer.md: 追加の質問", "README.md: 学習メモ"])
    memo, faq, rd = (read(pre, n) for n in ("02_explanation_memo.md", "11_question_and_answer.md", "README.md"))
    assert memo == memo_before  # 位置も含めて同じ
    assert faq == faq_before
    assert "### 在庫は回転で見る" in rd and rd.replace("### 在庫は回転で見る", "### 在庫は「回った回数」で見る") == rd_before
    assert "- 自分の店では90日ではなく60日にする。" in memo
    m = json.loads(read(pre, "out/00_manifest.json"))
    assert {(x["file"], x["heading"]) for x in m["foreign_sections"]} == {
        ("02_explanation_memo.md", "私のメモ"), ("11_question_and_answer.md", "追加の質問"), ("README.md", "学習メモ")}
    assert failed_ids(pre) == []
    # 2 回目は差分なし
    p, r2 = assemble(pre)
    assert r2["written"] == []
    # 利用者の節を、スキルの外で書き換えると C-9 が落ちる
    edit(pre, "02_explanation_memo.md", "60日にする", "30日にする")
    assert failed_ids(pre) == ["C-9"]


# ---- 通し：scaffold → 取り込み → out/ → assemble → check_docs --------------------------------
def test_end_to_end_from_scaffold_to_all_pass(tmp_path):
    dest, r = ingest(tmp_path, "video.md")
    for f in sorted((GOLDEN_VIDEO / "out").glob("*.md")):
        if f.name != "00_run-report.md":
            shutil.copy(f, dest / "out" / f.name)
    p, res = assemble(dest)
    assert p.returncode == 0, p.stderr
    out = run_checks(str(dest))
    assert out["passed"], out
    assert (dest / "01_source.md").read_text(encoding="utf-8").count("<!-- source-body:start -->") == 1


def test_help_has_contract():
    p = run_script("assemble.py", "--help")
    assert p.returncode == 0
    for w in ("--dry-run", "MISSING_OUT_FILE", "NO_INPUT", "終了コード", "foreign_sections"):
        assert w in p.stdout


def test_trailing_separator_in_out05_is_tolerated(pre):
    """out/05 の末尾に `-----`・`[toTop]` を付けてしまっても、転記で二重にならない。"""
    p = pre / "out/05_group-analysis-1.md"
    p.write_text(p.read_text(encoding="utf-8").rstrip("\n") + "\n\n-----\n[toTop](#totoppage)\n", encoding="utf-8")
    assemble(pre)
    for n in FINALS + ["README.md"]:
        assert read(pre, n) == read(GOLDEN_VIDEO, n), n
