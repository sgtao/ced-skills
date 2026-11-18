"""check_explain.py の会話の記録の集計と、静的検査の負例を確かめる。
実行: python3 tests/test_check_explain.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_explain as ce  # noqa: E402


def tool(name, **inp):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}}


class TranscriptTest(unittest.TestCase):
    def stats(self, events):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.jsonl"
            p.write_text("\n".join(json.dumps(e) for e in events) + "\nnot json\n", encoding="utf-8")
            return ce.transcript_stats(p)

    def test_counts(self):
        s = self.stats([
            tool("AskUserQuestion", questions=[{}, {}, {}]),
            tool("AskUserQuestion", questions=[{}]),
            tool("WebSearch", query="x"),
            tool("Skill", skill="ced-url-to-md"),
            {"type": "user", "message": {"content": "hi"}},
        ])
        self.assertEqual(s["ask_calls"], 2)
        self.assertEqual(s["ask_questions"], [3, 1])
        self.assertEqual(s["websearch"], 1)
        self.assertEqual(s["skills"], ["ced-url-to-md"])

    def test_zero(self):
        self.assertEqual(self.stats([tool("Bash", command="ls")])["ask_calls"], 0)


class StaticNegativeTest(unittest.TestCase):
    GOOD = """## 手順
### 3. 解説メモを作る
- `ced-craft-explanation-docs` に「質問なしで」と渡す。読み手は `--audience` の値。話題として扱わない。補足は足す。
### 4. 解説スライドを作る
- 確定値（目的・情報ソース・ビジュアル・枚数・保存先）を渡す。
"""

    def test_good_passes(self):
        self.assertEqual(ce.quiet_pass_checks(self.GOOD), [])

    def test_missing_quiet_fails(self):
        self.assertTrue(ce.quiet_pass_checks(self.GOOD.replace("質問なしで", "")))

    def test_audience_as_topic_fails(self):
        self.assertTrue(ce.quiet_pass_checks(self.GOOD.replace("話題として扱わない", "")))

    def test_missing_confirmed_value_fails(self):
        self.assertTrue(ce.quiet_pass_checks(self.GOOD.replace("保存先", "")))


class M5StaticTest(unittest.TestCase):
    """v0.0.2 M5：入力の決め方の検査。現在の explain.md は合格し、規則を欠いた文は不合格になる。"""

    def test_current_explain_passes(self):
        text = ce.EXPLAIN.read_text(encoding="utf-8")
        self.assertEqual(ce.m5_checks(text), [])

    def test_text_without_collection_fails(self):
        text = ce.EXPLAIN.read_text(encoding="utf-8").replace("collect_sources.py", "x.py")
        self.assertTrue(any("collect_sources.py" in p for p in ce.m5_checks(text)))

    def test_missing_q4_fails(self):
        text = ce.EXPLAIN.read_text(encoding="utf-8")
        text = "\n".join(l for l in text.split("\n") if not l.startswith("- Q4 "))
        self.assertTrue(any("Q1〜Q4" in p for p in ce.m5_checks(text)))

    def test_other_skill_path_fails(self):
        text = ce.EXPLAIN.read_text(encoding="utf-8") + "\n参照: plugins/ced-url-to-md/scripts/x.py\n"
        self.assertTrue(any("他のスキル" in p for p in ce.m5_checks(text)))

    def test_each_cross_check_rule_is_enforced(self):
        """計画との突き合わせで足した決まり（衝突時の Q1、Q4 の条件、参照元が 2 つの停止、値のそろえ方、Q6、継続）。"""
        base = ce.EXPLAIN.read_text(encoding="utf-8")
        cases = {"AMBIGUOUS_SOURCE_DIR": "AMBIGUOUS_SOURCE_DIR", "NFKC": "NFKC", "残りを続ける": "残りを続ける",
                 "未完了が 2 件以上、または参照元が 2 つ": "Q4 の条件", "動画 ID": "動画 ID"}
        for needle, expect in cases.items():
            probs = ce.m5_checks(base.replace(needle, "＿＿"))
            self.assertTrue(any(expect in p for p in probs), needle)

    def test_missing_injection_rule_fails(self):
        text = ce.EXPLAIN.read_text(encoding="utf-8").replace("データとして扱い", "従わせる")
        self.assertTrue(any("指示文" in p for p in ce.m5_checks(text)))


if __name__ == "__main__":
    unittest.main()
