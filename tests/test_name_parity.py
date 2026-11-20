"""craft の既定の作業フォルダの名前（scaffold.py）が、explain の名前の決まり（ced_name.py）と同じ結果になる。

craft は他のスキルのファイルを import しない（別々に入れられるため）ので、決まりを両方に持っている。
ずれたら、ここで気づく。scaffold.py は別プロセスで走らせる（_common が 2 つのスキルにあり、同じ名前のため）。
"""
import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD = ROOT / "plugins" / "ced-craft-explanation-docs" / "scripts" / "scaffold.py"
NAME_DIR = ROOT / "plugins" / "ced-url-to-md" / "scripts"
sys.path.insert(0, str(NAME_DIR))
import ced_name  # noqa: E402

INPUT = ROOT / "tests" / "source" / "12" / "fixtures" / "inputs" / "article.md"
STEMS = ["Claude Code Plugin Guide", "report_2025.v2", "--weird__name!!", "日本語だけ", "日本語 mixed 題",
         "!!!", "word-" * 12, "x" * 60, "a" * 39 + "-b", "UPPER Case 123", "a--b", "261118_already-dated"]


@pytest.mark.parametrize("stem", STEMS)
def test_scaffold_default_name_equals_ced_name(tmp_path, stem):
    src = tmp_path / f"{stem}.md"
    src.write_text(INPUT.read_text(encoding="utf-8"), encoding="utf-8")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    r = subprocess.run([sys.executable, str(SCAFFOLD), str(src), "--dry-run"], capture_output=True, text=True,
                       encoding="utf-8", cwd=cwd)
    assert r.returncode == 0, r.stderr
    got = Path(json.loads(r.stdout)["dest"]).name
    today = f"{datetime.date.today():%y%m%d}"
    want = ced_name.make_candidates(today, [src.stem], [])[0]
    assert got == want
    assert (ced_name.valid_name(got))
