#!/usr/bin/env python3
"""合格条件 4：install.sh を一時 HOME で動かし、3 通りのスコープ・--uninstall・--dry-run を確かめる。

確かめること:
- --scope user・--scope project・--dir の各々で、ced- の 4 スキルが入る
- 同じ指定の --uninstall で、ced- の 4 つだけが消え、ほかのスキル（url-to-md などの元の名前を含む）は残る
- --dry-run は、インストールでもアンインストールでも、ファイルを 1 つも変えない
- --list-targets は claude を含み、未対応のツールは失敗する

使い方（リポジトリのトップから）: python3 tests/test_install.py
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INSTALL = REPO / "scripts" / "install.sh"
CED = ["ced-url-to-md", "ced-pdf-to-md-ja", "ced-craft-explanation-docs", "ced-websearch-slide-ja"]


def snapshot(root: Path):
    """フォルダ内の全ファイルの（相対パス, 内容のハッシュ）を返す。存在しなければ空。"""
    if not root.exists():
        return []
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out.append((str(p.relative_to(root)), hashlib.sha256(p.read_bytes()).hexdigest()))
    return out


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ced-install-"))
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SKILLS_DIR"}
        self.env["HOME"] = str(self.home)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_install(self, *args, cwd=None, stdin=""):
        return subprocess.run(["bash", str(INSTALL), *args], cwd=cwd or self.tmp, env=self.env,
                              input=stdin, capture_output=True, text=True, timeout=120)

    def user_dir(self):
        return self.home / ".claude" / "skills"

    def ced_present(self, root: Path):
        return sorted(n for n in CED if (root / n / "SKILL.md").exists())

    def seed_foreign(self, root: Path):
        """元の名前のスキルと、無関係なスキルを置く（消えてはいけないもの）。"""
        for name in ["url-to-md", "pdf-to-md-ja", "craft-explanation-docs", "websearch-slide-ja", "other-skill"]:
            d = root / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")

    def foreign_present(self, root: Path):
        return sorted(n for n in ["url-to-md", "pdf-to-md-ja", "craft-explanation-docs", "websearch-slide-ja", "other-skill"]
                      if (root / n / "SKILL.md").exists())

    # --- インストール ---------------------------------------------------------
    def test_scope_user_installs_four(self):
        r = self.run_install("--scope", "user", "-y")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.ced_present(self.user_dir()), sorted(CED))

    def test_scope_project_installs_four(self):
        proj = self.tmp / "proj"
        proj.mkdir()
        r = self.run_install("--scope", "project", "--project-dir", str(proj), "-y")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.ced_present(proj / ".claude" / "skills"), sorted(CED))

    def test_dir_installs_four(self):
        d = self.tmp / "custom-skills"
        r = self.run_install("--dir", str(d), "-y")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.ced_present(d), sorted(CED))

    # --- アンインストール ------------------------------------------------------
    def test_uninstall_removes_only_ced_four(self):
        for args in (["--scope", "user"],):
            self.seed_foreign(self.user_dir())
            self.assertEqual(self.run_install(*args, "-y").returncode, 0)
            r = self.run_install(*args, "--uninstall", "-y")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(self.ced_present(self.user_dir()), [])
            self.assertEqual(self.foreign_present(self.user_dir()),
                             ["craft-explanation-docs", "other-skill", "pdf-to-md-ja", "url-to-md", "websearch-slide-ja"])

    def test_uninstall_project_and_dir_remove_only_ced(self):
        proj = self.tmp / "proj"
        d = self.tmp / "custom"
        for target_root, args in [(proj / ".claude" / "skills", ["--scope", "project", "--project-dir", str(proj)]),
                                  (d, ["--dir", str(d)])]:
            self.seed_foreign(target_root)
            self.assertEqual(self.run_install(*args, "-y").returncode, 0)
            self.assertEqual(self.ced_present(target_root), sorted(CED))
            r = self.run_install(*args, "--uninstall", "-y")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(self.ced_present(target_root), [])
            self.assertIn("url-to-md", self.foreign_present(target_root))

    def test_install_overwrites_only_ced_and_keeps_foreign(self):
        self.seed_foreign(self.user_dir())
        self.assertEqual(self.run_install("--scope", "user", "-y").returncode, 0)
        self.assertEqual(self.ced_present(self.user_dir()), sorted(CED))
        self.assertIn("other-skill", self.foreign_present(self.user_dir()))

    # --- --dry-run ------------------------------------------------------------
    def test_dry_run_install_changes_nothing(self):
        self.seed_foreign(self.user_dir())
        before = snapshot(self.home)
        r = self.run_install("--scope", "user", "--dry-run", "-y")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(snapshot(self.home), before)
        self.assertIn("DRY-RUN", r.stdout)

    def test_dry_run_uninstall_changes_nothing(self):
        self.seed_foreign(self.user_dir())
        self.assertEqual(self.run_install("--scope", "user", "-y").returncode, 0)
        before = snapshot(self.home)
        r = self.run_install("--scope", "user", "--uninstall", "--dry-run", "-y")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(snapshot(self.home), before)
        self.assertEqual(self.ced_present(self.user_dir()), sorted(CED))

    # --- 一覧・エラー ----------------------------------------------------------
    def test_list_targets(self):
        r = self.run_install("--list-targets")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("claude", r.stdout)

    def test_unsupported_target_fails(self):
        r = self.run_install("--target", "copilot", "--dry-run", "-y")
        self.assertNotEqual(r.returncode, 0)

    def test_unknown_option_fails(self):
        r = self.run_install("--no-such-option")
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
