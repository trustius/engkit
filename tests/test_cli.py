import json

from engkit.errors import EXIT_CONFLICT, EXIT_FAILURE, EXIT_OK, EXIT_USAGE
from tests import fixtures
from tests.helpers import TempDirTest, resources_at, run_cli, skill_text, snapshot


class CliTest(TempDirTest):
    def test_help_and_version(self):
        for argv in (["--help"], ["install", "--help"], ["project", "generate", "--help"], ["stack", "validate", "--help"]):
            with self.subTest(argv=argv):
                code, out, _ = run_cli(argv)
                self.assertEqual(code, EXIT_OK)
                self.assertIn("usage:", out)
        self.assertIn("exit codes", run_cli(["--help"])[1])
        self.assertEqual(run_cli(["--version"])[0], EXIT_OK)

    def test_invalid_arguments(self):
        for argv in ([], ["bogus"], ["install", "x"], ["install", "x", "--target", "vim"],
                     ["install", "x", "--target", "claude", "--global", "--project-dir", "."],
                     ["project", "generate", "--replace-generated", "--recover-generated"]):
            with self.subTest(argv=argv):
                self.assertEqual(run_cli(argv)[0], EXIT_USAGE)

    def test_list_and_validate_real_catalog(self):
        code, out, _ = run_cli(["list"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("systematic-debugging", out)
        code, out, _ = run_cli(["list", "--json"])
        self.assertEqual(len(json.loads(out)["skills"]), 5)
        self.assertEqual(run_cli(["validate"])[0], EXIT_OK)
        self.assertEqual(run_cli(["validate", "code-review"])[0], EXIT_OK)

    def test_validate_failure_reports_path(self):
        root = self.make_toolkit({"broken": "---\nname: [\n---\n", "fine": skill_text("fine")})
        with resources_at(root):
            code, _, err = run_cli(["validate"])
            self.assertEqual(code, EXIT_FAILURE)
            self.assertIn(str(root / "skills" / "broken" / "SKILL.md"), err)
            self.assertIn("malformed YAML", err)
            self.assertEqual(run_cli(["validate", "fine"])[0], EXIT_OK)

    def test_install_project_default_cwd_and_conflict(self):
        project = self.make_project()
        code, out, _ = run_cli(["install", "code-review", "--target", "all"], cwd=project)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("installed", out)
        self.assertTrue((project / ".claude/skills/code-review/SKILL.md").is_file())
        self.assertTrue((project / ".agents/skills/code-review/SKILL.md").is_file())
        code, out, _ = run_cli(["install", "code-review", "--target", "all", "--project-dir", str(project)])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("already installed", out)
        (project / ".claude/skills/code-review/SKILL.md").write_text("mine")
        code, _, err = run_cli(["install", "code-review", "--target", "claude", "--project-dir", str(project)])
        self.assertEqual(code, EXIT_CONFLICT)
        self.assertIn("conflict", err)

    def test_install_global_uses_temp_home(self):
        code, _, _ = run_cli(["install", "implementation-planning", "--target", "all", "--global"])
        self.assertEqual(code, EXIT_OK)
        self.assertTrue((self.home / ".claude/skills/implementation-planning/SKILL.md").is_file())
        self.assertTrue((self.home / ".codex/skills/implementation-planning/SKILL.md").is_file())

    def test_install_unknown_skill_and_missing_project(self):
        self.assertEqual(run_cli(["install", "nope", "--target", "claude", "--project-dir", str(self.tmp)])[0], EXIT_FAILURE)
        self.assertNotEqual(run_cli(["install", "code-review", "--target", "claude", "--project-dir", str(self.tmp / "missing")])[0], EXIT_OK)

    def test_project_workflow_end_to_end(self):
        project = self.make_project("mono", fixtures.MONOREPO)
        before = snapshot(project)
        code, out, _ = run_cli(["project", "inspect", "--project-dir", str(project), "--json"])
        self.assertEqual(code, EXIT_OK)
        data = json.loads(out)
        self.assertTrue(data["read_only"])
        self.assertEqual(len(data["profile"]["components"]), 4)
        self.assertEqual(snapshot(project), before, "inspect writes nothing")
        code, out, _ = run_cli(["project", "generate", "--project-dir", str(project), "--dry-run"])
        self.assertEqual((code, snapshot(project)), (EXIT_OK, before))
        self.assertEqual(run_cli(["project", "generate", "--project-dir", str(project), "--target", "all"])[0], EXIT_OK)
        code, out, _ = run_cli(["project", "generate", "--project-dir", str(project), "--target", "all", "--json"])
        self.assertEqual(json.loads(out)["status"], "unchanged")
        self.assertEqual(run_cli(["project", "generate", "--project-dir", str(project)])[0], EXIT_CONFLICT)
        code, out, _ = run_cli(["project", "generate", "--project-dir", str(project), "--recover-generated"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("nothing-to-recover", out)

    def test_stack_validate_and_define(self):
        project = self.make_project("p", fixtures.custom_pack_files())
        stack = self.tmp / "stack.yaml"
        stack.write_text("schema_version: 1\nkind: stack\nid: w\ncomponents:\n  - id: svc\n    root: .\n    packs: [acme-widget]\n")
        code, out, _ = run_cli(["stack", "validate", "--file", str(stack), "--project-dir", str(project)])
        self.assertEqual(code, EXIT_OK, out)
        code, out, _ = run_cli(["stack", "validate", "--file", str(stack)], cwd=self.make_project("other"))
        self.assertEqual(code, EXIT_FAILURE, "stack file directory is not the registry context")
        self.assertEqual(run_cli(["project", "define", "--stack", str(stack), "--project-dir", str(project)])[0], EXIT_OK)
        self.assertTrue((project / ".engkit/project.yaml").is_file())

    def test_doctor_is_read_only(self):
        project = self.make_project("mono", fixtures.MONOREPO)
        run_cli(["install", "code-review", "--target", "claude", "--project-dir", str(project)])
        run_cli(["project", "generate", "--project-dir", str(project)])
        (project / ".claude/skills/code-review/SKILL.md").write_text("edited")
        (project / ".engkit/generated/PROJECT_CONTEXT.md").write_text("edited")
        before, home_before = snapshot(project), snapshot(self.home)
        code, out, _ = run_cli(["doctor", "--project-dir", str(project), "--json"])
        self.assertEqual((snapshot(project), snapshot(self.home)), (before, home_before))
        report = json.loads(out)
        self.assertEqual(report["generated_status"], "modified")
        text = json.dumps(report)
        self.assertIn("code-review: installed copy differs", text)
        self.assertIn("systematic-debugging: not installed", text)
        self.assertIn("ambiguous", text)
        self.assertEqual(code, EXIT_OK)

    def test_doctor_reports_incomplete_generation_as_error(self):
        project = self.make_project("p", fixtures.GO_CLI)
        run_cli(["project", "generate", "--project-dir", str(project)])
        (project / ".engkit/generation-transaction.json").write_text("{}")
        code, out, _ = run_cli(["doctor", "--project-dir", str(project), "--project-only"])
        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("generated context: incomplete", out)

    def test_existing_instruction_files_are_never_modified(self):
        project = self.make_project("p", {**fixtures.GO_CLI, "CLAUDE.md": "# mine\n", "AGENTS.md": "# also mine\n"})
        run_cli(["install", "code-review", "--target", "all", "--project-dir", str(project)])
        run_cli(["project", "generate", "--project-dir", str(project), "--target", "all"])
        (project / ".engkit/project.yaml").write_text("schema_version: 1\nproject: {name: p}\n")
        self.assertEqual(run_cli(["project", "generate", "--project-dir", str(project), "--target", "all",
                                  "--replace-generated"])[0], EXIT_OK)
        run_cli(["doctor", "--project-dir", str(project)])
        self.assertEqual((project / "CLAUDE.md").read_text(), "# mine\n")
        self.assertEqual((project / "AGENTS.md").read_text(), "# also mine\n")
