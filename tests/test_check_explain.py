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


if __name__ == "__main__":
    unittest.main()
