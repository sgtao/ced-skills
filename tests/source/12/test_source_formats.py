"""collect_sources.py が作る 3 形式（text・code・subtitle）の入力を、scaffold が受け取れることの検査（合格条件 5 の 12 側）。

- text・code は article、subtitle は video のプロファイルになる
- code の入力に {{ 〜 }} や TODO があっても、01_source.md はそのまま複製され、C-4 で止まらない
"""
from __future__ import annotations

import json

import pytest

from conftest import run_script
from check_docs import run_checks
from scaffold import decide_profile, FORMAT_TO_PROFILE


@pytest.mark.parametrize("fmt,profile", [("text", "article"), ("code", "article"), ("subtitle", "video")])
def test_new_formats_map_to_profiles(fmt, profile):
    assert FORMAT_TO_PROFILE[fmt] == profile
    assert decide_profile({"source_format": fmt}, "本文")[0] == profile


CODE_MD = (
    "---\n"
    'title: "main.py"\n'
    'source_path: "src/main.py"\n'
    "source_format: code\n"
    "source_sha256: abc\n"
    "retrieved_at: 2026-11-18T00:00:00+09:00\n"
    "---\n\n"
    "# main.py\n\n"
    "```python\n"
    "tmpl = '{{ name }}'  # TODO: 直す\n"
    "print(tmpl)\n"
    "```\n"
)


def test_code_input_with_placeholders_is_copied_verbatim_and_not_c4(tmp_path):
    src = tmp_path / "main.md"
    src.write_text(CODE_MD, encoding="utf-8")
    p = run_script("scaffold.py", src, "--dest", tmp_path / "dest")
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout)
    assert r["profile"] == "article"
    body = (tmp_path / "dest" / "01_source.md").read_text(encoding="utf-8")
    assert "{{ name }}" in body and "TODO" in body, "入力の本文は書き換えない"
    c4 = next(i for i in run_checks(str(tmp_path / "dest"), only={"C-4"})["items"] if i["id"] == "C-4")
    assert all(f["file"] != "01_source.md" for f in c4["findings"]), "入力の複製は C-4 の対象外"
