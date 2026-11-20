"""部分実行・再実行（P5）：既存の作業フォルダの状態の報告と、指定したステップだけ作り直したときの波及。"""
from __future__ import annotations

import json
import os
import shutil
import time

from conftest import GOLDEN_VIDEO, INPUTS, edit, run_script
from check_docs import run_checks

FINALS = ["02_explanation_memo.md", "11_question_and_answer.md", "12_LLM_prompts_as_guide.md", "README.md"]


def status(folder):
    p = run_script("scaffold.py", folder)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def snapshot(folder):
    return {p.relative_to(folder).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in folder.rglob("*") if p.is_file()}


# ---- 状態の報告（scaffold.py <フォルダ>）-------------------------------------------------
def test_status_of_complete_folder(golden):
    r = status(golden)
    assert r["mode"] == "existing_folder"
    assert r["missing_steps"] == []
    assert all(r["steps"].values()) and set(r["steps"]) == {"1", "2", "3", "4", "5", "6", "7", "8-A", "8-B", "9"}
    assert r["groups"] == ["在庫回転率の考え方", "計算と実践"]


def test_status_reports_missing_steps(golden):
    (golden / "out/08_faq.md").unlink()
    (golden / "out/05_group-analysis-2.md").unlink()
    (golden / "out/10_system-prompt.md").unlink()
    r = status(golden)
    assert r["missing_steps"] == ["4", "7", "8-B"]
    assert r["steps"]["1"] is True


def test_status_without_grouping_marks_group_step_missing(golden):
    (golden / "out/04_grouping.md").unlink()
    r = status(golden)
    assert "3" in r["missing_steps"] and "4" in r["missing_steps"]
    assert r["groups"] == []


def test_status_does_not_write(golden):
    before = snapshot(golden)
    status(golden)
    assert before == snapshot(golden)


def test_status_detects_changed_input(tmp_path):
    src = tmp_path / "in.md"
    shutil.copy(INPUTS / "article.md", src)
    p = run_script("scaffold.py", src)
    assert p.returncode == 0, p.stderr
    dest = tmp_path / "in_explained"
    r = status(dest)
    assert r["input_changed"] is False
    assert set(r["missing_steps"]) == {"1", "2", "3", "4", "5", "6", "7", "8-A", "8-B", "9"}
    # 利用者が入力を書き足した（実機確認で実際にあったこと）
    src.write_text(src.read_text(encoding="utf-8") + "\n## 追記\n\n後から足した節です。\n", encoding="utf-8")
    r = status(dest)
    assert r["input_changed"] is True
    assert "別名" in r["input_note"]
    # 作業フォルダの 01_source.md は古い複製のまま（勝手に直さない）
    assert "後から足した節" not in (dest / "01_source.md").read_text(encoding="utf-8")


def test_status_unknown_input_is_not_a_failure(golden):
    # 見本の manifest の入力パスは相対パスで、ここからは見つからない → 不明（失敗にしない）
    r = status(golden)
    assert r["input_changed"] is None and r["input_note"]
    (golden / "out/00_manifest.json").unlink()
    r = status(golden)
    assert r["input_changed"] is None


# ---- 指定したステップだけ作り直す（部分実行）-----------------------------------------------
def test_redo_one_step_changes_only_its_final_file(golden):
    """FAQ（Step 7）だけ作り直して転記し直すと、11 だけが変わり、ほかの最終ファイル・01 は更新時刻も変わらない。"""
    old = "月に2回入れ替わっているなら、回転率は月2回。"
    edit(golden, "out/08_faq.md", old, "月に2回入れ替わっていれば、回転率は月2回と言える。")
    before = snapshot(golden)
    time.sleep(0.05)  # 更新時刻の差が出るように
    p = run_script("assemble.py", golden)
    assert p.returncode == 0, p.stderr
    res = json.loads(p.stdout)
    assert res["written"] == ["11_question_and_answer.md"]
    after = snapshot(golden)
    changed = {k for k in after if before[k][0] != after[k][0]}
    assert changed == {"11_question_and_answer.md"}
    for k in after:
        if k != "11_question_and_answer.md":
            assert after[k][1] == before[k][1], f"{k} の更新時刻が変わった"
    assert run_checks(str(golden))["passed"]


def test_rewriting_out_file_with_same_content_changes_nothing(golden):
    t =(golden / "out/06_summary.md").read_text(encoding="utf-8")
    (golden / "out/06_summary.md").write_text(t.rstrip("\n") + "\n", encoding="utf-8")  # 内容が同じなら何も変わらない
    before = snapshot(golden)
    p = run_script("assemble.py", golden)
    assert json.loads(p.stdout)["written"] == []
    assert before == snapshot(golden)


def test_partial_run_leaves_unspecified_mtimes(golden):
    """検査だけ・--dry-run は、どのファイルの更新時刻も変えない。"""
    before = snapshot(golden)
    for args in (("assemble.py", golden, "--dry-run"), ("check_docs.py", golden), ("scaffold.py", golden)):
        run_script(*args)
    assert before == snapshot(golden)
