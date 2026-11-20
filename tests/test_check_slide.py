"""check_slide_render.py（本文が html に残るか）と check_slide_variety.py（型・区切り・強調）の負例と正例を確かめる。
実行: uv run --python 3.12 pytest -q tests/test_check_slide.py
見本: tests/fixtures/slides/simple（1119-01 の簡素だった版）、remade（1119-02 の作り替えた版）。
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
RENDER = HERE / "check_slide_render.py"
VARIETY = HERE / "check_slide_variety.py"
FIX = HERE / "fixtures" / "slides"


def run(script, *args):
    r = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


class RenderTest(unittest.TestCase):
    def render(self, md, html):
        return run(RENDER, "--md", str(md), "--html", str(html))

    def test_simple_sample_keeps_its_lines(self):
        # 簡素だった版は、本文の行は html に残っている（簡素さは variety の検査で見る）
        code, out = self.render(FIX / "simple" / "01_source-slides.md", FIX / "simple" / "01_source-slides.html")
        self.assertEqual(code, 0, out)

    def test_dropped_sources_note_fails(self):
        # sources 型でリンク以外の注記が消えた負例（html の注記の span を取り除く）
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            html = (FIX / "simple" / "01_source-slides.html").read_text(encoding="utf-8")
            cut = re.sub(r'<span class="src-note">[^<]*</span>', "", html)
            self.assertNotEqual(html, cut)
            (d / "s.md").write_text((FIX / "simple" / "01_source-slides.md").read_text(encoding="utf-8"), encoding="utf-8")
            (d / "s.html").write_text(cut, encoding="utf-8")
            code, out = self.render(d / "s.md", d / "s.html")
            self.assertEqual(code, 1, out)
            self.assertIn("自動生成字幕", out)

    def test_remade_sample_passes(self):
        code, out = self.render(FIX / "remade" / "01_source-slides.md", FIX / "remade" / "01_source-slides.html")
        self.assertEqual(code, 0, out)

    def test_dropped_point_in_html_fails(self):
        # 作り替えた版から、本文の 1 行を html の側だけ消した負例
        with tempfile.TemporaryDirectory() as d:
            html = (FIX / "remade" / "01_source-slides.html").read_text(encoding="utf-8")
            target = "ジャグジー1杯分"
            self.assertIn(target, html)
            d = Path(d)
            (d / "s.md").write_text((FIX / "remade" / "01_source-slides.md").read_text(encoding="utf-8"), encoding="utf-8")
            (d / "s.html").write_text(html.replace(target, ""), encoding="utf-8")
            code, out = self.render(d / "s.md", d / "s.html")
            self.assertEqual(code, 1, out)
            self.assertIn("ジャグジー", out)

    def test_missing_args_exit_2(self):
        code, _ = run(RENDER)
        self.assertEqual(code, 2)


class VarietyTest(unittest.TestCase):
    def variety(self, md):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.md"
            p.write_text(md, encoding="utf-8")
            return run(VARIETY, str(p))

    def test_simple_sample_fails(self):
        code, out = run(VARIETY, str(FIX / "simple" / "01_source-slides.md"))
        self.assertEqual(code, 1, out)
        self.assertIn("tone: dark", out)
        self.assertIn("==", out)

    def test_remade_sample_passes(self):
        code, out = run(VARIETY, str(FIX / "remade" / "01_source-slides.md"))
        self.assertEqual(code, 0, out)

    def test_points_and_table_only_fails(self):
        md = (
            "---\ntitle: t\n---\n<!-- slide: points -->\n## a\n- **x**：y\n---\n"
            "<!-- slide: table -->\n## b\n| a | b |\n|---|---|\n| 1 | 2 |\n"
        )
        code, out = self.variety(md)
        self.assertEqual(code, 1, out)

    def test_varied_with_dark_and_emphasis_passes(self):
        md = (
            "---\ntitle: t\n---\n<!-- slide: title, tone: dark -->\n# 題\n---\n"
            "<!-- slide: steps -->\n## ==強調==\n```steps\nitems:\n  - title: a\n    desc: b\n```\n---\n"
            "<!-- slide: chart-bar -->\n## c\n"
        )
        code, out = self.variety(md)
        self.assertEqual(code, 0, out)


class ExplainSpecTest(unittest.TestCase):
    """explain.md の確定値（ビジュアル）に D11 の指定があるか（合格条件 4）。"""

    def visual_line(self):
        text = (HERE.parent / "plugins" / "commands" / "explain.md").read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if "ビジュアル:" in ln]
        self.assertTrue(lines, "explain.md にビジュアルの確定値が無い")
        # 確定値の行（インデントした箇条）の続き行も含める
        i = text.splitlines().index(lines[0])
        block = [lines[0]]
        for ln in text.splitlines()[i + 1 :]:
            if not ln.startswith("    ") and not ln.startswith("  -"):
                break
            block.append(ln)
        return "\n".join(block)

    def test_d11_items_present(self):
        v = self.visual_line()
        for needle in ("steps", "tone: dark", "==強調==", "badge:"):
            self.assertIn(needle, v, v)

    def test_confirmed_mode_names_the_slide_types(self):
        text = (HERE.parent / "plugins" / "ced-websearch-slide-ja" / "workflows" / "create.md").read_text(encoding="utf-8")
        i = text.index("確定値モード（呼び出し元が確定値を渡したとき）")
        block = text[i : i + 1500]
        for needle in ("steps", "tone: dark", "==強調==", "badge:", "sources", "points"):
            self.assertIn(needle, block)

    def test_sources_type_not_used_for_citations(self):
        v = self.visual_line()
        self.assertIn("sources", v, v)
        self.assertIn("points", v, v)
        self.assertIn("リンク", v, v)


if __name__ == "__main__":
    unittest.main()
