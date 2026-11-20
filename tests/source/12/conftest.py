"""テストの共通設定。スクリプトを import できるようにし、見本のフォルダを用意する。"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SUITE = Path(__file__).resolve().parent  # tests/source/12
ROOT = SUITE.parents[2]  # ced-skills のトップ
SCRIPTS = ROOT / "plugins" / "ced-craft-explanation-docs" / "scripts"
FIXTURES = SUITE / "fixtures"
INPUTS = FIXTURES / "inputs"
GOLDEN_VIDEO = FIXTURES / "golden" / "video"

sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def golden(tmp_path):
    """合格する見本（手作り）の作業フォルダの複製。テストの中で壊してよい。"""
    dst = tmp_path / "video"
    shutil.copytree(GOLDEN_VIDEO, dst)
    return dst


def run_script(name: str, *args, cwd=None):
    """scripts/<name> を別プロセスで実行して CompletedProcess を返す（UTF-8）。"""
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *[str(a) for a in args]],
        capture_output=True, text=True, encoding="utf-8", cwd=cwd,
    )


def edit(folder: Path, name: str, old: str, new: str, count: int = 1):
    """folder/name の old を new に置き換える（old が無ければ失敗。壊し方が古くなったことに気づける）。"""
    p = Path(folder) / name
    t = p.read_text(encoding="utf-8")
    assert t.count(old) >= 1, f"{name} に {old!r} が無い"
    p.write_text(t.replace(old, new, count), encoding="utf-8")
