"""単独で使った craft の出力（今いるフォルダ直下の YYMMDD_<名前>/）が、出力の形の検査に合格する（V3-M2・合格条件 9）。

見本ではなく、scaffold.py・assemble.py・check_docs.py を実際に走らせて作る。LLM が書く部分（out/ の中間ファイル、
README・01_source.md の埋め込み）とスライドだけは、見本・決まった文面で代わりに入れる。確かめるのは形で、生成の質ではない。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import GOLDEN_VIDEO, ROOT, default_dest, run_script
from test_ingest import ingest

LAYOUT = ROOT / "tests" / "check_output_layout.py"


def layout(folder: Path):
    r = subprocess.run([sys.executable, str(LAYOUT), str(folder), "--json"], capture_output=True, text=True,
                       encoding="utf-8")
    return r.returncode, json.loads(r.stdout)["problems"]


def test_standalone_output_passes_the_layout_check(tmp_path):
    # 1. 既定の場所に作る（--dest なし）。今いるフォルダ（tmp_path/cwd）の直下に YYMMDD_<名前>/ ができる
    dest, _ = ingest(tmp_path, "video.md")
    assert dest == default_dest("video")
    # 2. 中間ファイル（LLM が書く分。見本から）を置いて、assemble.py で最終の 5 ファイルを作り、check_docs.py に通す
    for f in sorted((GOLDEN_VIDEO / "out").glob("*.md")):
        if f.name != "00_run-report.md":
            shutil.copy(f, dest / "out" / f.name)
    a = run_script("assemble.py", dest)
    assert a.returncode == 0, a.stderr
    c = run_script("check_docs.py", dest)
    assert c.returncode == 0, c.stdout + c.stderr
    # 3. 解説スライドは直下の docs/ に置く（explain の形と同じ）。名前は日付を除いた名前
    body = dest.name.split("_", 1)[1]
    (dest / "docs").mkdir()
    (dest / "docs" / f"{body}-slides.md").write_text("# 見本\n", encoding="utf-8")
    (dest / "docs" / f"{body}-slides.html").write_text("<!doctype html><title>見本</title>\n", encoding="utf-8")
    # 4. 中間ファイル（out/）は、explain.md の決まりどおり .work/out/ へ移す（直下には置かない）。
    #    移す前は、形の検査が out/ を指摘する（検査が働いていることの確認）。
    code, problems = layout(dest)
    assert code == 1 and any("out/" in x for x in problems), problems
    (dest / ".work").mkdir()
    shutil.move(str(dest / "out"), str(dest / ".work" / "out"))
    code, problems = layout(dest)
    assert code == 0 and problems == [], problems


def test_old_default_shape_next_to_the_input_fails_the_layout_check(tmp_path):
    """v0.0.2 の既定（入力の隣の <名前>_explained/）の形は、検査が不合格にする。"""
    old = tmp_path / "video_explained"
    (old / "docs").mkdir(parents=True)
    for f in ("README.md", "01_source.md", "02_explanation_memo.md", "11_question_and_answer.md",
              "12_LLM_prompts_as_guide.md"):
        (old / f).write_text("x", encoding="utf-8")
    code, problems = layout(old)
    assert code == 1 and problems


def test_explain_flow_prepare_then_scaffold_into_the_out_dir(tmp_path):
    """explain.md の流れ：collect_sources.py prepare が <出力先>/.work/ を作り、そのあと同じ <出力先> に scaffold する。"""
    prepare = ROOT / "plugins" / "ced-url-to-md" / "scripts" / "collect_sources.py"
    src = Path.cwd() / "01_sources"
    src.mkdir()
    shutil.copy(ROOT / "tests" / "source" / "12" / "fixtures" / "inputs" / "article.md", src / "a.md")
    out = Path.cwd() / "261120_article"
    p = subprocess.run([sys.executable, str(prepare), "prepare", "--out-dir", str(out)],
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    md = next((out / ".work" / "md").glob("*.md"))
    s = run_script("scaffold.py", md, "--dest", out)
    assert s.returncode == 0, s.stderr
    assert (out / "01_source.md").is_file() and (out / ".work" / "sources.json").is_file()
