#!/usr/bin/env python3
"""合格条件 9 の見本の検査（v0.0.3 の形）：合格の見本 2 つが合格し、不合格の見本 5 つが不合格になる。
実行: python3 tests/test_check_output_layout.py（または uv run pytest tests/test_check_output_layout.py）"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_output_layout import check_layout  # noqa: E402

FX = Path(__file__).resolve().parent / "fixtures" / "layout"
OK_SINGLE = FX / "ok-single" / "261118_claude-code-plugin-guide"
OK_MULTI = FX / "ok-multi" / "261120_report-pack"
BAD = {
    "bad-v002-shape": "261118_report",          # v0.0.2 の形（explained/・直下のスライド）
    "bad-no-date": "report-guide",              # 日付の無い名前
    "bad-long-name": "261118_this-name-is-far-too-long-for-the-folder-rule-here",  # 40 文字超
    "bad-slides-outside-docs": "261118_plugin-guide",  # スライドが docs/ の外
    "bad-intermediate-at-top": "261118_plugin-guide",  # 直下の中間ファイル
}


class LayoutTest(unittest.TestCase):
    def copy_single(self, tmp):
        d = Path(tmp) / "261118_claude-code-plugin-guide"
        shutil.copytree(OK_SINGLE, d)
        return d

    def test_ok_shapes_pass(self):
        self.assertEqual(check_layout(OK_SINGLE), [])
        self.assertEqual(check_layout(OK_MULTI), [])

    def test_bad_shapes_fail(self):
        for sub, name in BAD.items():
            with self.subTest(sub):
                self.assertTrue(check_layout(FX / sub / name))

    def test_v002_shape_reports_explained_folder(self):
        probs = check_layout(FX / "bad-v002-shape" / "261118_report")
        self.assertTrue(any("explained/" in p for p in probs), probs)

    def test_multi_without_index_link_fails(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "261120_report-pack"
            shutil.copytree(OK_MULTI, d)
            (d / "00_index.md").write_text("# 一覧\n- stock-review\n", encoding="utf-8")
            self.assertTrue(any("calc-stock" in p for p in check_layout(d)))

    def test_single_with_extra_memo_file_fails(self):
        with tempfile.TemporaryDirectory() as t:
            d = self.copy_single(t)
            (d / "notes.md").write_text("x", encoding="utf-8")
            self.assertTrue(check_layout(d))

    def test_slide_name_must_match_name_without_date(self):
        with tempfile.TemporaryDirectory() as t:
            d = self.copy_single(t)
            (d / "docs" / "claude-code-plugin-guide-slides.md").rename(d / "docs" / "x-slides.md")
            (d / "docs" / "claude-code-plugin-guide-slides.html").rename(d / "docs" / "x-slides.html")
            self.assertTrue(any("スライドの名前" in p for p in check_layout(d)))

    def test_slide_name_keeps_the_date_out(self):
        # スライドの名前に日付を付けたら不合格（名前は日付を除く。D14）
        with tempfile.TemporaryDirectory() as t:
            d = self.copy_single(t)
            (d / "docs" / "claude-code-plugin-guide-slides.md").rename(d / "docs" / "261118_claude-code-plugin-guide-slides.md")
            (d / "docs" / "claude-code-plugin-guide-slides.html").rename(d / "docs" / "261118_claude-code-plugin-guide-slides.html")
            self.assertTrue(check_layout(d))

    def test_child_name_with_date_fails(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "261120_report-pack"
            shutil.copytree(OK_MULTI, d)
            (d / "stock-review").rename(d / "261120_stock-review")
            self.assertTrue(any("261120_stock-review" in p for p in check_layout(d)))

    def test_broken_index_link_fails(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "261120_report-pack"
            shutil.copytree(OK_MULTI, d)
            (d / "00_index.md").write_text("# 一覧\n- [stock-review](stock-review/explained/README.md)\n", encoding="utf-8")
            self.assertTrue(any("リンク先が無い" in p for p in check_layout(d)))

    def test_work_folder_is_not_checked(self):
        with tempfile.TemporaryDirectory() as t:
            d = self.copy_single(t)
            (d / ".work" / "any").mkdir(parents=True)
            (d / ".work" / "any" / "x.md").write_text("x", encoding="utf-8")
            self.assertEqual(check_layout(d), [])


if __name__ == "__main__":
    unittest.main()
