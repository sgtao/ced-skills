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

    def test_os_junk_files_are_ignored_but_real_extras_still_fail(self):
        # macOS が Finder で作る .DS_Store は、どこにあっても形の検査で無視する（実物の出力で H2 が落ちたため）。
        # 無視するのは OS の屑ファイルだけで、ほかの余分なファイルは今までどおり不合格
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "261120_report-pack"
            shutil.copytree(OK_MULTI, d)
            junk = [d / ".DS_Store", d / "stock-review" / ".DS_Store", d / "stock-review" / "docs" / ".DS_Store",
                    d / "stock-review" / ".work" / ".DS_Store"]
            for j in junk:
                j.write_bytes(b"\0")
            self.assertEqual(check_layout(d), [])
            (d / "stock-review" / "notes.md").write_text("x", encoding="utf-8")
            self.assertTrue(any("notes.md" in p for p in check_layout(d)))
        with tempfile.TemporaryDirectory() as t:
            d = self.copy_single(t)
            (d / ".DS_Store").write_bytes(b"\0")
            (d / "docs" / ".DS_Store").write_bytes(b"\0")
            self.assertEqual(check_layout(d), [])

    def test_index_link_must_name_the_child_not_a_substring(self):
        # reviewer の低：子の名前が短い（a・d）と、索引に `md` があるだけで `d` のリンクがあると判定された
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "261120_report-pack"
            shutil.copytree(OK_MULTI, d)
            (d / "stock-review").rename(d / "a")
            (d / "calc-stock").rename(d / "d")
            (d / "00_index.md").write_text("# 一覧\n- [a](a/README.md)\n- 解説メモ（md）\n", encoding="utf-8")
            link = lambda: [p for p in check_layout(d) if "へのリンクが無い" in p]  # noqa: E731（名前を変えたのでスライド名の指摘は別）
            self.assertEqual(link(), ["00_index.md に d へのリンクが無い"])
            (d / "00_index.md").write_text("# 一覧\n- [a](a/README.md)\n- [d](d/README.md)\n", encoding="utf-8")
            self.assertEqual(link(), [])

    def test_a_folder_named_ds_store_is_not_ignored(self):
        # reviewer の低：無視するのは屑ファイルだけ。`.DS_Store` という名前のフォルダは、中身ごと不合格にする
        with tempfile.TemporaryDirectory() as t:
            d = self.copy_single(t)
            (d / ".DS_Store").mkdir()
            self.assertTrue(check_layout(d))

    def test_a_child_with_a_non_d13_name_still_fails(self):
        # L4 の再発防止：slug 由来の `calc_stock.py` のような名前は、.DS_Store を無視するようにしても不合格のまま
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "261120_report-pack"
            shutil.copytree(OK_MULTI, d)
            (d / "stock-review").rename(d / "e2e-input__stock-review.pdf")
            self.assertTrue(any("e2e-input__stock-review.pdf" in p for p in check_layout(d)))

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
