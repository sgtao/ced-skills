"""テストの共通設定。スクリプトを import できるようにし、見本のフォルダを用意する。"""
from __future__ import annotations

import re
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


# ---- 既定の作業フォルダ（V3-M2：今いるフォルダの直下の YYMMDD_<名前>/）-------------------------------
_ROOT_IGNORE = {".venv", ".pytest_cache", "__pycache__", ".git", ".ruff_cache"}


def default_dest(stem: str, today=None, cwd=None) -> Path:
    """既定の作業フォルダの期待値。規則は仕様から作る（日付は実行した日。固定しない）。

    名前は ced_name.py と同じ決まり：英小文字・数字・-（それ以外は - にまとめる）、40 文字以内で単語の切れ目、
    英字が無ければ source。
    """
    import datetime
    import os
    day = today or datetime.date.today()
    body = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    if len(body) > 40:
        head = body[:41]
        k = head.rfind("-")
        body = body[:k if k > 0 else 40].rstrip("-")
    return Path(cwd or os.getcwd()) / f"{day:%y%m%d}_{body or 'source'}"


@pytest.fixture(autouse=True)
def _cwd_in_tmp(tmp_path, monkeypatch):
    """既定の場所に頼るテストが、リポジトリに何も作らないようにする。

    カレントを、入力とは別の一時フォルダにする（既定の作業フォルダはここにできる）。
    テストの後で、ced-skills のトップの直下が変わっていないことも確かめる。
    """
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    before = sorted(p.name for p in ROOT.iterdir() if p.name not in _ROOT_IGNORE)
    yield cwd
    after = sorted(p.name for p in ROOT.iterdir() if p.name not in _ROOT_IGNORE)
    assert after == before, f"テストが ced-skills のフォルダに作った: {sorted(set(after) - set(before))}"
