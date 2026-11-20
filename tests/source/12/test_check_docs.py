"""check_docs.py（C-1〜C-12）のテスト。

- 手作りの合格見本（tests/fixtures/golden/video/）は全項目 PASS。
- 合格見本を 1 か所だけ壊すと、壊した項目だけが FAIL（C-1〜C-11 のそれぞれ）。
- 検査の側は変えない。見本が検査を通るように直すのは、見本の側。
"""
from __future__ import annotations

import json
import shutil

import pytest

from conftest import GOLDEN_VIDEO, edit, run_script
from check_docs import run_checks

ALL_IDS = [f"C-{i}" for i in range(1, 13)]


def failed_ids(folder):
    r = run_checks(str(folder))
    return [i["id"] for i in r["items"] if i["status"] == "FAIL"]


def findings(folder, cid):
    r = run_checks(str(folder))
    return next(i for i in r["items"] if i["id"] == cid)["findings"]


# ---- 合格見本 ----------------------------------------------------------------------
def test_golden_passes_all_items(golden):
    r = run_checks(str(golden))
    assert [i["id"] for i in r["items"]] == ALL_IDS
    assert all(i["status"] == "PASS" for i in r["items"]), r
    assert r["passed"] is True
    assert r["summary"] == {"pass": 12, "fail": 0}


def test_golden_committed_folder_passes_without_copy():
    """リポジトリに入っている見本そのもの（out/ を含む）が検査に通る。"""
    assert (GOLDEN_VIDEO / "out" / "00_manifest.json").is_file()
    assert run_checks(str(GOLDEN_VIDEO))["passed"] is True


# ---- 壊した見本：1 か所だけ壊すと、その項目だけ FAIL ---------------------------------
def break_c1(d):
    (d / "12_LLM_prompts_as_guide.md").unlink()


def break_c1_manifest(d):
    (d / "out" / "00_manifest.json").unlink()


def break_c2(d):
    edit(d, "README.md", "## 概要", "## 要旨")


def break_c2_order(d):
    # 解説の中の見出しの順序を入れ替える（「4. ユースケース」を「1. 要約」の前に出す）
    edit(d, "02_explanation_memo.md", "### 4. ユースケース", "### 1. 要約", count=1)


def break_c3(d):
    edit(d, "02_explanation_memo.md", "### 4. ユースケース", "### 4. ユースケース\n詳細は out/05_group-analysis-1.md を参照。")


def break_c4(d):
    edit(d, "11_question_and_answer.md", "### 1. この動画は何を扱っているのか", "### 1. この動画は何を扱っているのか\nTODO: あとで書く")


def break_c5(d):
    edit(d, "README.md", "(./02_explanation_memo.md)", "(./02_memo.md)")


def break_c5_anchor(d):
    edit(d, "README.md", "(./02_explanation_memo.md)", "(./02_explanation_memo.md#存在しない見出し)")


def break_c6(d):
    edit(d, "02_explanation_memo.md", "### 2. 例え話", "在庫は大切である。" * 60 + "\n\n### 2. 例え話")


def break_c6_count_label(d):
    """活用案の末尾の「（N字）」を、実測と違う数にする。"""
    import re
    p = d / "02_explanation_memo.md"
    t = p.read_text(encoding="utf-8")
    m = re.search(r"（(\d+)字）", t)
    p.write_text(t[:m.start()] + f"（{int(m.group(1)) + 5}字）" + t[m.end():], encoding="utf-8")


def break_c7(d):
    """セクション 6「まとめ」を、02 の「セクション別の解説」から落とす（見出しと根拠の行の両方）。"""
    edit(d, "02_explanation_memo.md", "#### 6. まとめ（04:50〜05:20）", "#### 6. 終わりに（04:50〜05:20）")
    edit(d, "02_explanation_memo.md", "セクション6 まとめ [04:50]", "セクション6 終わりに [04:50]")


def break_c8(d):
    edit(d, "02_explanation_memo.md", "計算式は売上原価を平均在庫で割るだけです", "計算式は売上原価を月商で割るだけです")


def break_c9(d):
    edit(d, "01_source.md", "在庫回転立という物差し", "在庫回転率という物差し")


def break_c10(d):
    edit(d, "11_question_and_answer.md", "- `title`: 5分でわかる在庫の回し方（在庫回転率の基本）", "- `title`: 別の題名")


def break_c12(d):
    # 横断分析の 3 つ目の視点（子箇条書き）を消して、視点を 2 個にする
    edit(d, "README.md", "\n  - 数字を月ごとに測る習慣が、感覚では気づけない滞留を見つける。", "")


def break_c11(d):
    edit(d, "01_source.md", "- 解説の入口：[README.md](./README.md)\n", "")


BREAKERS = {
    "C-1": [break_c1, break_c1_manifest],
    "C-2": [break_c2, break_c2_order],
    "C-3": [break_c3],
    "C-4": [break_c4],
    "C-5": [break_c5, break_c5_anchor],
    "C-6": [break_c6, break_c6_count_label],
    "C-7": [break_c7],
    "C-8": [break_c8],
    "C-9": [break_c9],
    "C-10": [break_c10],
    "C-11": [break_c11],
    "C-12": [break_c12],
}


@pytest.mark.parametrize("cid,breaker", [(c, b) for c, bs in BREAKERS.items() for b in bs],
                         ids=lambda v: v if isinstance(v, str) else v.__name__)
def test_broken_sample_fails_only_that_item(golden, cid, breaker):
    breaker(golden)
    assert failed_ids(golden) == [cid]


def test_every_item_has_a_breaker():
    assert sorted(BREAKERS, key=lambda s: int(s[2:])) == ALL_IDS


# ---- 個別の確かめ ------------------------------------------------------------------
def test_findings_have_file_line_message(golden):
    break_c3(golden)
    f = findings(golden, "C-3")
    assert len(f) == 1
    assert f[0]["file"] == "02_explanation_memo.md"
    assert isinstance(f[0]["line"], int)
    assert "out/" in f[0]["message"]


def test_c4_ignores_placeholders_inside_code_blocks_of_02(golden):
    """02 のコードブロックは本文のコードの引用なので、{{ があってもプレースホルダとして扱わない。"""
    edit(golden, "02_explanation_memo.md", "### 4. ユースケース", "### 4. ユースケース\n```\n{{ name }}\n```")
    assert "C-4" not in failed_ids(golden)


def test_c4_checks_code_block_of_system_prompt(golden):
    edit(golden, "12_LLM_prompts_as_guide.md", "# 役割", "# 役割\n{{role}}")
    assert failed_ids(golden) == ["C-4"]


def test_c5_checks_top_page_link_on_line_1(golden):
    """1 行目の toTopPage は ./README.md（作業フォルダの中）を指し、C-5 で飛び先を確かめる。"""
    assert (golden / "README.md").read_text(encoding="utf-8").startswith("###### [toTopPage](./README.md)")
    assert "C-5" not in failed_ids(golden)


def test_c5_fails_when_top_page_points_outside_the_work_folder(golden):
    """../README.md は作業フォルダの外（explained/ の上）を指すので、飛べない。"""
    edit(golden, "README.md", "###### [toTopPage](./README.md)", "###### [toTopPage](" + "../README.md)")
    assert "C-5" in failed_ids(golden)


def test_c5_link_outside_folder_fails(golden):
    edit(golden, "README.md", "- [01_source.md](./01_source.md)", "- [x](../outside.md)")
    f = findings(golden, "C-5")
    assert any("外" in x["message"] for x in f)


def test_c5_anchor_into_source_body_headings(tmp_path):
    """見出しのある入力（article）では、README の目次リンク（01_source.md#…）の見出しを確かめる。"""
    d = tmp_path / "w"
    shutil.copytree(GOLDEN_VIDEO, d)
    # 本文に見出しがある形にして、README から本文の見出しへ飛ぶ
    edit(d, "README.md", "- 1 : はじめに ｜ 00:00〜00:40", "- 1 : [はじめに](./01_source.md#概要) ｜ 00:00〜00:40")
    edit(d, "01_source.md", "- 1 : はじめに ｜ 00:00〜00:40", "- 1 : [はじめに](#概要) ｜ 00:00〜00:40")
    assert failed_ids(d) == []  # 本文に `## 概要` がある
    edit(d, "README.md", "01_source.md#概要", "01_source.md#存在しない見出し")
    assert failed_ids(d) == ["C-5"]


def test_c6_counts_each_limit(golden):
    r = run_checks(str(golden), only={"C-6"})
    assert r["items"][0]["status"] == "PASS"
    # ポイントまとめ（70 字）
    edit(golden, "02_explanation_memo.md", "在庫は売れて初めてお金になるので、回転率で測る。", "あ" * 71)
    assert any("ポイントまとめ" in f["message"] for f in findings(golden, "C-6"))


def test_c6_system_prompt_limit(golden):
    edit(golden, "12_LLM_prompts_as_guide.md", "# 役割", "あ" * 2001 + "\n# 役割")
    f = findings(golden, "C-6")
    assert len(f) == 1 and "システムプロンプト" in f[0]["message"]


def test_c6_reflection_over_400(golden):
    import re
    p = golden / "02_explanation_memo.md"
    t = p.read_text(encoding="utf-8")
    t = t.replace("まずは1か月だけ試し", "あ" * 400 + "まずは1か月だけ試し", 1)
    t = re.sub(r"(案1：店長の視点\n)(.+?)（\d+字）", lambda m: m.group(1) + m.group(2) + "（%d字）" % __import__("_common").char_count(m.group(2)), t, flags=re.S)
    p.write_text(t, encoding="utf-8")
    f = findings(golden, "C-6")
    assert len(f) == 1 and "上限 400" in f[0]["message"], f


def test_c8_allows_ellipsis_marker_and_whitespace_differences(golden):
    # 中略で 2 つに分けた引用は、それぞれが本文にあれば合格。空白・改行の違いは無視する
    edit(golden, "02_explanation_memo.md",
         "「計算式は売上原価を平均在庫で割るだけです」",
         "「計算式は…（中略）…割る だけです」")
    assert "C-8" not in failed_ids(golden)


def test_c9_crlf_in_source_is_normalized(golden):
    """複製の本文の改行が CRLF になっていても、LF にそろえて比べる。"""
    p = golden / "01_source.md"
    raw = p.read_bytes().replace(b"\n", b"\r\n")
    p.write_bytes(raw)
    assert failed_ids(golden) == []


def test_c9_trailing_newlines_are_normalized(golden):
    p = golden / "01_source.md"
    p.write_text(p.read_text(encoding="utf-8") + "\n\n\n", encoding="utf-8")
    assert failed_ids(golden) == []


def test_c9_foreign_section_unchanged_then_changed(golden):
    """スキルが作っていない節（利用者が足した節）が変わると C-9 が落ちる。"""
    from _common import normalize_body, section_text, sha256_text
    p = golden / "README.md"
    t = p.read_text(encoding="utf-8")
    extra = "## 学習メモ（利用者）\n- 私のメモ\n\n"
    t = t.replace("-----\n[toTop](#totoppage)\n## 本文", "-----\n[toTop](#totoppage)\n" + extra + "-----\n[toTop](#totoppage)\n## 本文", 1)
    p.write_text(t, encoding="utf-8")
    sec = section_text(t, "学習メモ（利用者）", 2)
    mp = golden / "out" / "00_manifest.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    m["foreign_sections"] = [{"file": "README.md", "heading": "学習メモ（利用者）", "level": 2,
                              "sha256": sha256_text(normalize_body(sec))}]
    mp.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    assert failed_ids(golden) == []
    edit(golden, "README.md", "- 私のメモ", "- 書き換えられたメモ")
    assert failed_ids(golden) == ["C-9"]


def test_c10_group_names_must_match(golden):
    edit(golden, "11_question_and_answer.md", "## FAQ｜グループ2：計算と実践", "## FAQ｜グループ2：別の名前")
    assert failed_ids(golden) == ["C-10"]


def test_c10_toc_must_match_readme(golden):
    edit(golden, "01_source.md", "- 2 : 在庫回転率とは ｜ 00:40〜01:50", "- 2 : 在庫回転率とは ｜ 00:40〜01:40")
    assert failed_ids(golden) == ["C-10"]


def test_no_sections_means_no_toc_and_no_list(golden):
    """分割なしの入力：01_source.md に目次が無く、README のセクションも「分割なし」。"""
    import re
    p = golden / "01_source.md"
    t = p.read_text(encoding="utf-8")
    t = re.sub(r"## セクション目次\n(?:- .*\n)+\n-----\n\[toTop\]\(#totoppage\)\n", "", t)
    t = t.replace("-----\n[toTop](#totoppage)\n\n<!-- source-body:start -->", "<!-- source-body:start -->")
    p.write_text(t, encoding="utf-8")
    r = golden / "README.md"
    rt = r.read_text(encoding="utf-8")
    rt = re.sub(r"動画の概要欄のチャプターによる区切りです。\n\n(?:- \d : .*\n)+", "分割なし\n", rt)
    r.write_text(rt, encoding="utf-8")
    # 目次が無い（README に件数あり）→ 揃えれば合格する。C-7 は対象が無いので合格
    assert failed_ids(golden) == [], findings(golden, "C-10")


def test_missing_files_do_not_crash(tmp_path):
    (tmp_path / "w").mkdir()
    r = run_checks(str(tmp_path / "w"))
    assert r["passed"] is False
    assert [i["id"] for i in r["items"] if i["status"] == "FAIL"] == ["C-1"]


# ---- CLI ---------------------------------------------------------------------------
def test_cli_pass_exit_0_and_text_report(golden):
    p = run_script("check_docs.py", golden)
    assert p.returncode == 0, p.stderr
    assert "PASS  C-1" in p.stdout and "結果: 12 PASS / 0 FAIL" in p.stdout
    assert "REASON=" not in p.stderr


def test_cli_fail_exit_1_with_reason_lines(golden):
    break_c8(golden)
    p = run_script("check_docs.py", golden)
    assert p.returncode == 1
    last3 = p.stderr.strip().splitlines()[-3:]
    assert last3[0].startswith("[stop] ") and "C-8" in last3[0]
    assert last3[1].startswith("[next] ")
    assert last3[2] == "REASON=CHECK_FAILED"
    assert "FAIL  C-8" in p.stdout
    assert "02_explanation_memo.md:" in p.stdout  # 場所が出る


def test_cli_json_shape(golden):
    break_c3(golden)
    p = run_script("check_docs.py", golden, "--json")
    assert p.returncode == 1
    data = json.loads(p.stdout)
    assert set(data) == {"schema", "folder", "passed", "summary", "items"}
    assert data["schema"] == 1 and data["passed"] is False
    assert data["summary"] == {"pass": 11, "fail": 1}
    item = next(i for i in data["items"] if i["id"] == "C-3")
    assert set(item) == {"id", "name", "status", "findings"}
    assert item["status"] == "FAIL"
    assert set(item["findings"][0]) == {"file", "line", "message"}
    ok = next(i for i in data["items"] if i["id"] == "C-1")
    assert ok["status"] == "PASS" and ok["findings"] == []


def test_cli_json_pass_exit_0(golden):
    p = run_script("check_docs.py", golden, "--json")
    assert p.returncode == 0
    assert json.loads(p.stdout)["passed"] is True


def test_cli_only(golden):
    break_c8(golden)
    p = run_script("check_docs.py", golden, "--only", "C-1,C-3", "--json")
    assert p.returncode == 0
    assert [i["id"] for i in json.loads(p.stdout)["items"]] == ["C-1", "C-3"]


def test_cli_unknown_item_exit_2(golden):
    p = run_script("check_docs.py", golden, "--only", "C-99")
    assert p.returncode == 2


def test_cli_missing_folder_no_input(tmp_path):
    p = run_script("check_docs.py", tmp_path / "nothing")
    assert p.returncode == 1
    assert p.stderr.strip().splitlines()[-1] == "REASON=NO_INPUT"


def test_cli_help_has_contract():
    p = run_script("check_docs.py", "--help")
    assert p.returncode == 0
    for word in ("--json", "--only", "終了コード", "CHECK_FAILED", "NO_INPUT", "C-11"):
        assert word in p.stdout


def test_cli_does_not_modify_folder(golden):
    before = {p: p.read_bytes() for p in golden.rglob("*") if p.is_file()}
    run_script("check_docs.py", golden)
    after = {p: p.read_bytes() for p in golden.rglob("*") if p.is_file()}
    assert before == after


def test_c8_checks_non_bold_evidence_lines_too(golden):
    """太字でない「根拠：」の行も照合する。根拠でない行の「…」は照合しない。"""
    edit(golden, "02_explanation_memo.md", "- **根拠**：セクション1 はじめに [00:20]「在庫は持っているだけではお金を生みません売れて初めてお金に変わります」",
         "- 根拠：セクション1 はじめに [00:20]「本文に無い文章です」")
    assert failed_ids(golden) == ["C-8"]


def test_c8_ignores_quotes_on_non_evidence_lines(golden):
    edit(golden, "02_explanation_memo.md", "### 4. ユースケース", "### 4. ユースケース\n- 注：用語「本文に無い言葉」の説明。")
    assert "C-8" not in failed_ids(golden)


def test_c4_does_not_check_verbatim_input_copy(golden):
    """01_source.md は入力の複製なので、入力にある {{ や TODO は残りものではない（C-4 の対象外）。"""
    edit(golden, "01_source.md", "# ", "TODO: 入力の一部\n{{ name }}\n# ")
    assert [f for f in findings(golden, "C-4") if f["file"] == "01_source.md"] == []
