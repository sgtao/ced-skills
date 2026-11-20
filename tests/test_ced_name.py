"""V3-M2（合格条件 9）：出力フォルダ名の候補を作る ced_name.py の検査。

D13：名前は `YYMMDD_<英小文字と数字と ->`。`_` の後ろは 40 文字以内（単語の切れ目で切る）。
候補は 3 つ。英訳・要約の候補を受け取り、整えて、重複と既にある名前を避ける。
見本：日本語の題・記号・長い題・空の題・重複・既にある名前。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "ced-url-to-md" / "scripts" / "ced_name.py"
sys.path.insert(0, str(SCRIPT.parent))

import ced_name  # noqa: E402

NAME_RE = re.compile(r"^[0-9]{6}_[a-z0-9]+(-[a-z0-9]+)*$")


def body(name):
    return name.split("_", 1)[1]


def check_shape(names):
    assert len(names) == 3
    assert len(set(names)) == 3, "候補が重なっている"
    for n in names:
        assert NAME_RE.match(n), n
        assert len(body(n)) <= 40, n


def test_plain_english_titles_give_three_names():
    names = ced_name.make_candidates("261118", ["Claude Code Plugin Guide", "Building plugins for Claude Code", "cc plugin basics"], [])
    check_shape(names)
    assert names[0] == "261118_claude-code-plugin-guide"


def test_japanese_title_is_not_used_as_is():
    # 日本語の題は、英訳を先に渡す約束。日本語のまま渡されたら、その候補は捨てる
    names = ced_name.make_candidates("261118", ["Claude Codeのプラグイン入門", "claude-code-plugin-intro"], [])
    check_shape(names)
    assert all(ord(c) < 128 for n in names for c in n)
    assert "261118_claude-code-plugin-intro" in names


def test_symbols_are_turned_into_single_hyphens():
    names = ced_name.make_candidates("261118", ["  Report: Q3 / 2026!!  (final) ", "a__b..c", "x&y"], [])
    check_shape(names)
    assert "261118_report-q3-2026-final" in names
    assert "261118_a-b-c" in names


def test_long_title_is_cut_at_a_word_boundary_within_40():
    long = "this is a very long title that keeps going well past forty characters for sure"
    names = ced_name.make_candidates("261118", [long], [])
    check_shape(names)
    first = body(names[0])
    assert len(first) <= 40
    assert long.startswith(first.replace("-", " ")), first  # 単語の途中で切らない


def test_long_word_without_hyphen_is_hard_cut():
    names = ced_name.make_candidates("261118", ["a" * 60], [])
    check_shape(names)
    assert len(body(names[0])) == 40


def test_empty_title_falls_back_without_breaking_the_shape():
    names = ced_name.make_candidates("261118", ["", "   ", "!!!"], [])
    check_shape(names)
    assert names[0] == "261118_source"


def test_duplicate_candidates_are_removed():
    names = ced_name.make_candidates("261118", ["Plugin Guide", "plugin-guide", "Plugin Guide!"], [])
    check_shape(names)
    assert names[0] == "261118_plugin-guide"
    assert names[1] == "261118_source"  # 重複の後は、空の題と同じ既定で埋める


def test_existing_folder_gets_a_suffix():
    names = ced_name.make_candidates("261118", ["plugin guide"], ["261118_plugin-guide"])
    check_shape(names)
    assert "261118_plugin-guide" not in names
    assert "261118_plugin-guide-2" in names


def test_suffix_keeps_the_40_limit():
    base = "x" * 39
    names = ced_name.make_candidates("261118", [base], ["261118_" + base])
    check_shape(names)
    assert names[0].endswith("-2") and len(body(names[0])) <= 40


def test_bad_date_is_rejected():
    with pytest.raises(ValueError):
        ced_name.make_candidates("2611", ["x"], [])
    with pytest.raises(ValueError):
        ced_name.make_candidates("261340", ["x"], [])  # 13 月は無い


def test_cli_prints_json_list(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), "--date", "261118", "--title", "Plugin Guide",
                        "--title", "Plugin basics", "--existing", str(tmp_path)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    names = json.loads(r.stdout)
    check_shape(names)
