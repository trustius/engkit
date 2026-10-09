import json
import shutil
import unittest

from engkit.errors import EXIT_CONFLICT, EXIT_FAILURE, EXIT_OK, EXIT_USAGE
from tests.helpers import TempDirTest, make_repo, resources_at, run_cli, skill_text, snapshot


class CliTest(TempDirTest):
    def test_help_and_version(self):
        for argv in (["--help"], ["install", "--help"], ["doctor", "--help"]):
            with self.subTest(argv=argv):
                code, out, _ = run_cli(argv)
                self.assertEqual(code, EXIT_OK)
                self.assertIn("usage:", out)
        self.assertIn("exit codes", run_cli(["--help"])[1])
        self.assertEqual(run_cli(["--version"])[0], EXIT_OK)

    def test_invalid_arguments(self):
        for argv in (
            [],
            ["bogus"],
            ["install", "x"],
            ["install", "x", "--target", "vim"],
            ["install", "x", "--target", "claude", "--global", "--project-dir", "."],
        ):
            with self.subTest(argv=argv):
                self.assertEqual(run_cli(argv)[0], EXIT_USAGE)

    def test_list_and_validate_real_catalog(self):
        code, out, _ = run_cli(["list"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("bug-investigate", out)
        code, out, _ = run_cli(["list", "--json"])
        self.assertEqual(len(json.loads(out)["skills"]), 7)
        self.assertEqual(run_cli(["validate"])[0], EXIT_OK)
        self.assertEqual(run_cli(["validate", "change-review"])[0], EXIT_OK)

    def test_validate_failure_reports_path(self):
        root = self.make_skills_dir({"broken": "---\nname: [\n---\n", "fine": skill_text("fine")})
        with resources_at(root):
            code, _, err = run_cli(["validate"])
            self.assertEqual(code, EXIT_FAILURE)
            self.assertIn(str(root / "broken" / "SKILL.md"), err)
            self.assertIn("malformed YAML", err)
            self.assertEqual(run_cli(["validate", "fine"])[0], EXIT_OK)

    def test_install_project_default_cwd_and_conflict(self):
        project = self.make_project()
        code, out, _ = run_cli(["install", "change-review", "--target", "all"], cwd=project)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("installed", out)
        self.assertTrue((project / ".claude/skills/change-review/SKILL.md").is_file())
        self.assertTrue((project / ".agents/skills/change-review/SKILL.md").is_file())
        code, out, _ = run_cli(
            ["install", "change-review", "--target", "all", "--project-dir", str(project)]
        )
        self.assertEqual(code, EXIT_OK)
        self.assertIn("already installed", out)
        (project / ".claude/skills/change-review/SKILL.md").write_text("mine")
        code, _, err = run_cli(
            ["install", "change-review", "--target", "claude", "--project-dir", str(project)]
        )
        self.assertEqual(code, EXIT_CONFLICT)
        self.assertIn("conflict", err)

    def test_install_global_uses_temp_home(self):
        code, _, _ = run_cli(["install", "plan-implement", "--target", "all", "--global"])
        self.assertEqual(code, EXIT_OK)
        self.assertTrue((self.home / ".claude/skills/plan-implement/SKILL.md").is_file())
        self.assertTrue((self.home / ".agents/skills/plan-implement/SKILL.md").is_file())

    def test_install_unknown_skill_and_missing_project(self):
        self.assertEqual(
            run_cli(["install", "nope", "--target", "claude", "--project-dir", str(self.tmp)])[0],
            EXIT_FAILURE,
        )
        self.assertNotEqual(
            run_cli(
                [
                    "install",
                    "change-review",
                    "--target",
                    "claude",
                    "--project-dir",
                    str(self.tmp / "missing"),
                ]
            )[0],
            EXIT_OK,
        )

    def test_removed_project_commands_are_unknown(self):
        for argv in (["project", "inspect"], ["stack", "validate", "--file", "x.yaml"]):
            with self.subTest(argv=argv):
                self.assertEqual(run_cli(argv)[0], EXIT_USAGE)

    def test_doctor_is_read_only(self):
        project = self.make_project("p", {"README.md": "x"})
        run_cli(["install", "change-review", "--target", "claude", "--project-dir", str(project)])
        (project / ".claude/skills/change-review/SKILL.md").write_text("edited")
        before, home_before = snapshot(project), snapshot(self.home)
        code, out, _ = run_cli(["doctor", "--project-dir", str(project), "--json"])
        self.assertEqual((snapshot(project), snapshot(self.home)), (before, home_before))
        text = json.dumps(json.loads(out))
        self.assertIn("change-review: installed copy differs", text)
        self.assertIn("bug-investigate: not installed", text)
        self.assertEqual(code, EXIT_OK)

    def test_existing_instruction_files_are_never_modified(self):
        files = {"CLAUDE.md": "# mine\n", "AGENTS.md": "# also mine\n"}
        project = self.make_project("p", files)
        run_cli(["install", "change-review", "--target", "all", "--project-dir", str(project)])
        run_cli(["doctor", "--project-dir", str(project)])
        self.assertEqual((project / "CLAUDE.md").read_text(), "# mine\n")
        self.assertEqual((project / "AGENTS.md").read_text(), "# also mine\n")

    def test_memory_init_and_validate(self):
        project = self.make_project("p", {"CLAUDE.md": "# mine\n"})
        code, out, _ = run_cli(["memory", "init", "--project-dir", str(project)])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("@.engkit/memory/INDEX.md", out)
        self.assertEqual((project / "CLAUDE.md").read_text(), "# mine\n")
        self.assertIn(
            "kept existing", run_cli(["memory", "init", "--project-dir", str(project)])[1]
        )
        self.assertEqual(run_cli(["memory", "validate", "--project-dir", str(project)])[0], EXIT_OK)
        (project / ".engkit/memory/broken.md").write_text("no frontmatter\n")
        self.assertEqual(
            run_cli(["memory", "validate", "--project-dir", str(project)])[0], EXIT_FAILURE
        )
        code, out, _ = run_cli(["doctor", "--project-dir", str(project), "--project-only"])
        self.assertIn("== Project memory", out)


class LifecycleCliTest(TempDirTest):
    def test_install_argument_rules(self):
        remote = ["--source", "file:///nowhere"]
        for argv in (
            ["install", "--target", "claude"],
            ["install", "x", "--target", "claude", "--skill", "y"],
            ["install", "x", "--target", "claude", "--ref", "main"],
            ["install", "x", "--target", "claude", "--path", "d"],
            ["install", "--target", "claude", *remote],
            ["install", "x", "--target", "claude", "--skill", "y", *remote],
            ["list", "--ref", "main"],
            ["uninstall", "--target", "claude"],
        ):
            with self.subTest(argv=argv):
                self.assertEqual(run_cli(argv)[0], EXIT_USAGE)

    def test_builtin_install_update_uninstall(self):
        project = self.make_project()
        where = ["--project-dir", str(project)]
        run_cli(["install", "change-review", "--target", "all", *where])
        code, out, _ = run_cli(["update", *where])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("up to date", out)
        code, out, _ = run_cli(["uninstall", "change-review", "--target", "claude", *where])
        self.assertEqual((code, "uninstalled" in out), (EXIT_OK, True))
        self.assertFalse((project / ".claude/skills/change-review").exists())
        code, _, err = run_cli(["uninstall", "change-review", "--target", "claude", *where])
        self.assertEqual((code, "not managed" in err), (EXIT_FAILURE, True))
        (project / ".agents/skills/change-review/SKILL.md").write_text("mine")
        code, _, err = run_cli(["uninstall", "change-review", "--target", "codex", *where])
        self.assertEqual((code, "conflict" in err), (EXIT_CONFLICT, True))

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_list_source(self):
        repo = make_repo(self.tmp / "remote", {"skills/demo/SKILL.md": skill_text("demo")})
        code, out, _ = run_cli(["list", "--source", f"file://{repo}", "--json"])
        self.assertEqual(code, EXIT_OK)
        self.assertEqual([item["name"] for item in json.loads(out)["skills"]], ["demo"])
