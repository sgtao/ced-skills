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
        r = self.run_install("--target", "vscode", "--dry-run", "-y")
        self.assertNotEqual(r.returncode, 0)

    def test_unknown_option_fails(self):
        r = self.run_install("--no-such-option")
        self.assertNotEqual(r.returncode, 0)


# ---- v0.0.2 M6：多ツール（PLAN 6 節の表） -------------------------------------------
# (--target, --scope) → 配置先（HOME と プロジェクトのフォルダからの相対）
TARGET_DIRS = {
    ("claude", "user"): [".claude/skills"],
    ("claude", "project"): [".claude/skills"],
    ("agents", "user"): [".agents/skills"],
    ("agents", "project"): [".agents/skills"],
    ("copilot", "user"): [".copilot/skills"],
    ("copilot", "project"): [".github/skills"],
    ("antigravity", "user"): [".gemini/config/skills"],
    ("antigravity", "project"): [".agents/skills"],
    ("all", "user"): [".claude/skills", ".agents/skills", ".gemini/config/skills"],
    ("all", "project"): [".claude/skills", ".agents/skills"],
}
FOREIGN = ["url-to-md", "pdf-to-md-ja", "craft-explanation-docs", "websearch-slide-ja", "other-skill"]


class MultiTargetTest(unittest.TestCase):
    """PLAN 6 節：--target（claude・agents・copilot・antigravity・all）と --scope（user・project）。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ced-multi-"))
        self.home = self.tmp / "home"
        self.proj = self.tmp / "proj"
        self.home.mkdir()
        self.proj.mkdir()
        self.env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SKILLS_DIR"}
        self.env["HOME"] = str(self.home)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_install(self, *args):
        return subprocess.run(["bash", str(INSTALL), *args], cwd=self.proj, env=self.env,
                              input="", capture_output=True, text=True, timeout=120)

    def dirs(self, target, scope):
        base = self.home if scope == "user" else self.proj
        return [base / d for d in TARGET_DIRS[(target, scope)]]

    def args(self, target, scope, yes=True):
        a = ["--target", target, "--scope", scope]
        if scope == "project":
            a += ["--project-dir", str(self.proj)]
        return a + (["-y"] if yes else [])

    def seed_foreign_everywhere(self, target, scope):
        for d in self.dirs(target, scope):
            d.mkdir(parents=True, exist_ok=True)
            for name in FOREIGN:
                (d / name).mkdir(exist_ok=True)
                (d / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")

    def ced_in(self, d: Path):
        return sorted(n for n in CED if (d / n / "SKILL.md").exists())

    def test_every_target_and_scope_installs_into_the_listed_places(self):
        for (target, scope) in TARGET_DIRS:
            with self.subTest(target=target, scope=scope):
                r = self.run_install(*self.args(target, scope))
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                for d in self.dirs(target, scope):
                    self.assertEqual(self.ced_in(d), sorted(CED), str(d))

    def test_all_user_does_not_leave_ced_elsewhere(self):
        """all は、列挙した 3 か所だけに入る。claude 以外の場所に、余分な複製を作らない。"""
        r = self.run_install(*self.args("all", "user"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for rel in [".copilot/skills", ".github/skills"]:
            self.assertFalse((self.home / rel).exists(), rel)

    def test_all_project_installs_once_per_directory(self):
        r = self.run_install(*self.args("all", "project"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        listed = [ln for ln in r.stdout.splitlines() if ln.startswith("配置先:")]
        self.assertEqual(len(listed), len(set(listed)), listed)
        self.assertEqual(len(listed), 2, listed)

    def test_uninstall_removes_only_ced_four_for_each_target(self):
        for (target, scope) in TARGET_DIRS:
            with self.subTest(target=target, scope=scope):
                self.seed_foreign_everywhere(target, scope)
                self.assertEqual(self.run_install(*self.args(target, scope)).returncode, 0)
                r = self.run_install(*self.args(target, scope), "--uninstall")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                for d in self.dirs(target, scope):
                    self.assertEqual(self.ced_in(d), [], str(d))
                    self.assertEqual(sorted(n for n in FOREIGN if (d / n / "SKILL.md").exists()), sorted(FOREIGN), str(d))

    def test_dry_run_changes_nothing_for_all_targets(self):
        for (target, scope) in TARGET_DIRS:
            with self.subTest(target=target, scope=scope):
                self.seed_foreign_everywhere(target, scope)
                before = snapshot(self.home) + snapshot(self.proj)
                r = self.run_install(*self.args(target, scope, yes=False), "--dry-run", "-y")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(snapshot(self.home) + snapshot(self.proj), before)
                r = self.run_install(*self.args(target, scope, yes=False), "--uninstall", "--dry-run", "-y")
                self.assertEqual(snapshot(self.home) + snapshot(self.proj), before)

    def test_aliases_codex_and_gemini_mean_agents(self):
        for alias in ("codex", "gemini"):
            with self.subTest(alias=alias):
                r = self.run_install("--target", alias, "--scope", "user", "-y")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(self.ced_in(self.home / ".agents/skills"), sorted(CED))

    def test_list_targets_names_every_target(self):
        r = self.run_install("--list-targets")
        self.assertEqual(r.returncode, 0, r.stderr)
        for name in ("claude", "agents", "copilot", "antigravity", "all"):
            self.assertIn(name, r.stdout)

    def test_option_without_value_reports_the_option(self):
        """B4：--scope の値を省くと、黙って止まらずに、何が足りないかを伝える。"""
        for opt in ("--scope", "--target", "--dir", "--project-dir"):
            with self.subTest(opt=opt):
                r = self.run_install(opt)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(opt, r.stderr)

    def test_help_starts_with_the_title_not_a_rule_line(self):
        """B4：--help の先頭の行は、罫線ではなく題。"""
        r = self.run_install("--help")
        self.assertEqual(r.returncode, 0)
        first = r.stdout.splitlines()[0]
        self.assertIn("install.sh", first)
        self.assertNotIn("====", r.stdout)

    def test_dir_with_target_all_is_an_error_but_single_target_is_fine(self):
        d = self.tmp / "custom"
        before = snapshot(self.tmp)
        r = self.run_install("--target", "all", "--dir", str(d), "-y")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(snapshot(self.tmp), before)
        r = self.run_install("--target", "copilot", "--dir", str(d), "-y")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.ced_in(d), sorted(CED))

    def test_warns_when_project_has_both_claude_and_agents(self):
        """Copilot は .claude/skills と .agents/skills の両方を読むので、両方に入れるときは警告する。"""
        r = self.run_install(*self.args("all", "project"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("WARN", r.stderr)
        # 片方を入れた後で、もう片方を入れるときも警告する
        self.assertEqual(self.run_install(*self.args("agents", "project"), "--uninstall").returncode, 0)
        r = self.run_install(*self.args("claude", "project"))
        self.assertNotIn("WARN", r.stderr)  # .claude に入れ直すだけで、.agents は空
        self.assertEqual(self.run_install(*self.args("agents", "project")).returncode, 0)
        r = self.run_install(*self.args("agents", "project"))
        self.assertIn("WARN", r.stderr)

    def test_no_warning_for_a_single_tool_or_user_scope(self):
        for target, scope in (("claude", "project"), ("agents", "project"), ("all", "user"), ("copilot", "project")):
            with self.subTest(target=target, scope=scope):
                self.setUp_clean()
                r = self.run_install(*self.args(target, scope))
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertNotIn("WARN", r.stderr)

    def setUp_clean(self):
        shutil.rmtree(self.proj, ignore_errors=True)
        shutil.rmtree(self.home, ignore_errors=True)
        self.proj.mkdir()
        self.home.mkdir()

    def test_unknown_target_fails_and_writes_nothing(self):
        before = snapshot(self.home) + snapshot(self.proj)
        r = self.run_install("--target", "vscode", "--scope", "user", "-y")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(snapshot(self.home) + snapshot(self.proj), before)


# ---- v0.0.2 M7：ced-explain は claude 以外に入り、claude には入らない ---------------------
class ExplainSkillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ced-explain-"))
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SKILLS_DIR"}
        self.env["HOME"] = str(self.home)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_install(self, *args):
        return subprocess.run(["bash", str(INSTALL), *args], cwd=self.tmp, env=self.env,
                              input="", capture_output=True, text=True, timeout=120)

    def test_claude_user_does_not_get_ced_explain(self):
        r = self.run_install("--target", "claude", "--scope", "user", "-y")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.home / ".claude/skills/ced-explain").exists())
        self.assertEqual(sorted(n for n in CED if (self.home / ".claude/skills" / n / "SKILL.md").exists()), sorted(CED))

    def test_other_targets_get_ced_explain_and_the_four(self):
        cases = [("agents", "user", ".agents/skills"), ("copilot", "user", ".copilot/skills"),
                 ("antigravity", "user", ".gemini/config/skills"), ("agents", "project", None)]
        for target, scope, rel in cases:
            with self.subTest(target=target, scope=scope):
                args = ["--target", target, "--scope", scope, "-y"]
                if scope == "project":
                    args += ["--project-dir", str(self.tmp)]
                    rel = ".agents/skills" if target == "agents" else rel
                r = self.run_install(*args)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                d = (self.home if scope == "user" else self.tmp) / rel
                self.assertTrue((d / "ced-explain" / "SKILL.md").is_file(), str(d))
                self.assertEqual(sorted(n for n in CED if (d / n / "SKILL.md").is_file()), sorted(CED))

    def test_all_user_puts_explain_only_outside_claude(self):
        r = self.run_install("--target", "all", "--scope", "user", "-y")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.home / ".claude/skills/ced-explain").exists())
        self.assertTrue((self.home / ".agents/skills/ced-explain/SKILL.md").is_file())
        self.assertTrue((self.home / ".gemini/config/skills/ced-explain/SKILL.md").is_file())

    def test_claude_install_does_not_need_the_generated_adapter(self):
        """claude は ced-explain を使わないので、生成物（adapters/）が無くても入る。"""
        copy = self.tmp / "copy"
        (copy / "scripts").mkdir(parents=True)
        (copy / "plugins").mkdir()
        shutil.copy(INSTALL, copy / "scripts" / "install.sh")
        for name in CED:
            shutil.copytree(REPO / "plugins" / name, copy / "plugins" / name)
        r = subprocess.run(["bash", str(copy / "scripts" / "install.sh"), "--target", "claude", "--scope", "user", "-y"],
                           cwd=self.tmp, env=self.env, input="", capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(sorted(n for n in CED if (self.home / ".claude/skills" / n / "SKILL.md").exists()), sorted(CED))

    def test_non_claude_install_stops_without_the_adapter(self):
        copy = self.tmp / "copy"
        (copy / "scripts").mkdir(parents=True)
        (copy / "plugins").mkdir()
        shutil.copy(INSTALL, copy / "scripts" / "install.sh")
        for name in CED:
            shutil.copytree(REPO / "plugins" / name, copy / "plugins" / name)
        r = subprocess.run(["bash", str(copy / "scripts" / "install.sh"), "--target", "agents", "--scope", "user", "-y"],
                           cwd=self.tmp, env=self.env, input="", capture_output=True, text=True, timeout=120)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("ced-explain", r.stderr)
        self.assertFalse((self.home / ".agents/skills").exists(), "止まるときは何も入れない")

    def test_uninstall_removes_ced_explain_outside_claude(self):
        self.assertEqual(self.run_install("--target", "copilot", "--scope", "user", "-y").returncode, 0)
        d = self.home / ".copilot/skills"
        (d / "other-skill").mkdir()
        (d / "other-skill" / "SKILL.md").write_text("---\nname: other-skill\n---\n", encoding="utf-8")
        r = self.run_install("--target", "copilot", "--scope", "user", "--uninstall", "-y")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((d / "ced-explain").exists())
        self.assertTrue((d / "other-skill" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
