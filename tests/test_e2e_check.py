"""e2e_check.py の集計（1 件・2 件以上）。lint は差し替える（mdss-convert の結果には依らない）。

- 1 件：作業フォルダの直下に解説メモ 5 本と docs/ の 1 組
- 2 件以上：直下に 00_index.md と子のフォルダ（それぞれが 1 件の形）。子ごとに 7・8 を確かめる
実行: uv run --python 3.12 pytest -q -p no:cacheprovider tests/test_e2e_check.py
"""
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parent
GOLDEN = REPO / "tests" / "source" / "12" / "fixtures" / "golden" / "video"
spec = importlib.util.spec_from_file_location("e2e_check", TESTS / "e2e_check.py")
e2e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e2e)


def make_unit(folder: Path):
    """golden（合格する見本）を folder に写し、out/ を .work/out/ へ移す（explain と同じ）。docs/ に 1 組。"""
    shutil.copytree(GOLDEN, folder)
    (folder / ".work").mkdir()
    shutil.move(str(folder / "out"), str(folder / ".work" / "out"))
    (folder / "docs").mkdir()
    (folder / "docs" / f"{folder.name}-slides.md").write_text("---\ntitle: t\n---\n# x\n", encoding="utf-8")
    (folder / "docs" / f"{folder.name}-slides.html").write_text("<html></html>", encoding="utf-8")


@pytest.fixture
def lint_ok(monkeypatch):
    monkeypatch.setattr(e2e, "lint", lambda md: ({"error": 0, "warn": 0, "items": []}, None))


def run_main(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["e2e_check.py", *[str(a) for a in args], "--json", "--skip-layout"])
    code = e2e.main()
    return code, json.loads(capsys.readouterr().out)


def test_one_unit_passes(tmp_path, monkeypatch, capsys, lint_ok):
    make_unit(tmp_path / "work")
    code, rep = run_main(monkeypatch, capsys, tmp_path / "work")
    assert code == 0, rep
    assert all(rep["criteria"].values()), rep["criteria"]
    assert "7_units" not in rep["criteria"]


def test_two_units_each_checked_and_aggregated(tmp_path, monkeypatch, capsys, lint_ok):
    root = tmp_path / "root"
    root.mkdir()
    (root / "00_index.md").write_text("# index\n", encoding="utf-8")
    make_unit(root / "calc-stock")
    make_unit(root / "stock-review")
    code, rep = run_main(monkeypatch, capsys, root)
    assert code == 0, rep["criteria"]
    c = rep["criteria"]
    assert c["7_units"] is True
    for name in ("calc-stock", "stock-review"):
        for k in ("7_docs_folder", "7_check_docs", "7_slide_pair", "8_lint_zero"):
            assert c[f"{name}/{k}"] is True, (name, k)


def test_one_child_failing_is_named_and_fails_the_run(tmp_path, monkeypatch, capsys, lint_ok):
    root = tmp_path / "root"
    root.mkdir()
    (root / "00_index.md").write_text("# index\n", encoding="utf-8")
    make_unit(root / "calc-stock")
    make_unit(root / "stock-review")
    (root / "stock-review" / ".work" / "out" / "00_manifest.json").unlink()  # C-1 だけ落とす
    code, rep = run_main(monkeypatch, capsys, root)
    assert code == 1
    assert rep["criteria"]["stock-review/7_check_docs"] is False
    assert rep["criteria"]["calc-stock/7_check_docs"] is True


def test_lint_warn_in_one_child_fails_that_child(tmp_path, monkeypatch, capsys):
    root = tmp_path / "root"
    root.mkdir()
    (root / "00_index.md").write_text("# index\n", encoding="utf-8")
    make_unit(root / "calc-stock")
    make_unit(root / "stock-review")

    def lint(md):
        warn = 1 if "stock-review" in str(md) else 0
        return {"error": 0, "warn": warn, "items": []}, None

    monkeypatch.setattr(e2e, "lint", lint)
    code, rep = run_main(monkeypatch, capsys, root)
    assert code == 1
    assert rep["criteria"]["stock-review/8_lint_zero"] is False
    assert rep["criteria"]["calc-stock/8_lint_zero"] is True


def test_multi_root_with_one_unit_fails_7_units(tmp_path, monkeypatch, capsys, lint_ok):
    root = tmp_path / "root"
    root.mkdir()
    (root / "00_index.md").write_text("# index\n", encoding="utf-8")
    make_unit(root / "calc-stock")
    code, rep = run_main(monkeypatch, capsys, root)
    assert code == 1
    assert rep["criteria"]["7_units"] is False
