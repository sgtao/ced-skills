"""adapters/ced-explain/SKILL.md が、plugins/commands/explain.md から作った結果と一致している。

explain.md を直したあとに作り直し忘れると、Claude Code 以外のツールだけ古い手順になる（check_portable.py は
この一致を見ていない）。直すときは `python3 scripts/build_explain_skill.py`。
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_generated_adapter_matches_explain_md():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_explain_skill.py"), "--check"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
