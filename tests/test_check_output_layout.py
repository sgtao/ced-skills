#!/usr/bin/env python3
"""合格条件 8 の見本の検査：合格の見本 2 つが合格し、不合格の見本 3 つが不合格になる。実行: python3 tests/test_check_output_layout.py"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_output_layout import check_layout  # noqa: E402

FX = Path(__file__).resolve().parent / "fixtures" / "layout"


class LayoutTest(unittest.TestCase):
    def test_ok_shapes_pass(self):
        for n in ("ok-single", "ok-multi"):
            self.assertEqual(check_layout(FX / n), [], n)

    def test_bad_shapes_fail(self):
        for n in ("bad-explained-suffix", "bad-nested", "bad-source-at-top"):
            self.assertTrue(check_layout(FX / n), n)

    def test_multi_without_index_link_fails(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "o"
            shutil.copytree(FX / "ok-multi", d)
            (d / "00_index.md").write_text("# 一覧\n- src__main.py\n", encoding="utf-8")
            self.assertTrue(any("docs__guide.pdf" in p for p in check_layout(d)))

    def test_single_with_extra_memo_file_fails(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "o"
            shutil.copytree(FX / "ok-single", d)
            (d / "explained" / "notes.md").write_text("x", encoding="utf-8")
            self.assertTrue(check_layout(d))

    def test_slide_name_must_match_slug(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "o"
            shutil.copytree(FX / "ok-multi", d)
            (d / "src__main.py" / "src__main.py-slides.md").rename(d / "src__main.py" / "x-slides.md")
            (d / "src__main.py" / "src__main.py-slides.html").rename(d / "src__main.py" / "x-slides.html")
            self.assertTrue(any("スライドの名前" in p for p in check_layout(d)))


if __name__ == "__main__":
    unittest.main()
