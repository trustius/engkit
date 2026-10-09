"""engkit init: all built-in skills plus project memory, with platform detection."""

from __future__ import annotations

import json
from unittest import mock

from engkit import catalog
from tests.helpers import TempDirTest, run_cli, snapshot

CLAUDE_NEXT = "Next: open Claude Code here and run /engineering-onboard"
CODEX_NEXT = "Next: open Codex here and run $engineering-onboard"


def _which_only(*found: str):
    def fake(command: str):
        if command in found:
            return f"/usr/bin/{command}"
        return None

    return mock.patch("shutil.which", side_effect=fake)


class InitTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.project = self.make_project()
        self.names = [skill.name for skill in catalog.discover(catalog.builtin_skills_dir()).skills]

    def init(self, *extra: str):
        return run_cli(["init", "--project-dir", str(self.project), *extra])

    def test_fresh_project_all_targets(self):
        code, out, err = self.init("--target", "all")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.names), 6)
        for name in self.names:
            self.assertTrue((self.project / ".claude/skills" / name / "SKILL.md").is_file())
            self.assertTrue((self.project / ".agents/skills" / name / "SKILL.md").is_file())
        memory_dir = self.project / ".engkit/memory"
        self.assertTrue((memory_dir / "INDEX.md").is_file())
        self.assertTrue((memory_dir / ".gitignore").is_file())
        lock = json.loads((self.project / ".engkit/skills.lock.json").read_text())
        self.assertEqual(len(lock["skills"]), 6)
        self.assertIn("CLAUDE.md:", out)
        self.assertIn("installed 12, already installed 0, conflicts 0", out)
        self.assertIn(CLAUDE_NEXT, out)
        self.assertIn(CODEX_NEXT, out)

    def test_rerun_is_a_no_op(self):
        self.init("--target", "all")
        before = snapshot(self.project)
        code, out, err = self.init("--target", "all")
        self.assertEqual(code, 0, err)
        self.assertEqual(snapshot(self.project), before)
        self.assertIn("installed 0, already installed 12, conflicts 0", out)
        self.assertIn("kept existing", out)

    def test_one_conflict_does_not_block_the_rest(self):
        existing = self.project / ".claude/skills/change-review/SKILL.md"
        existing.parent.mkdir(parents=True)
        existing.write_text("different\n")
        code, out, err = self.init("--target", "claude")
        self.assertEqual(code, 3)
        self.assertEqual(existing.read_text(), "different\n")
        self.assertIn("conflicts 1", out + err)
        for name in self.names:
            if name != "change-review":
                self.assertTrue((self.project / ".claude/skills" / name / "SKILL.md").is_file())

    def test_global_installs_into_home_without_memory(self):
        cwd = self.make_project("elsewhere")
        code, out, err = run_cli(["init", "--global", "--target", "all"], cwd=cwd)
        self.assertEqual(code, 0, err)
        for name in self.names:
            self.assertTrue((self.home / ".claude/skills" / name / "SKILL.md").is_file())
            self.assertTrue((self.home / ".agents/skills" / name / "SKILL.md").is_file())
        self.assertFalse((cwd / ".engkit/memory").exists())
        self.assertFalse((self.home / ".engkit/memory").exists())
        self.assertIn("memory: skipped (--global)", out)

    def test_no_platform_detected(self):
        with _which_only():
            code, out, err = self.init()
        self.assertEqual(code, 2)
        self.assertIn("--target", err)
        self.assertEqual(snapshot(self.project), {})

    def test_detects_only_codex(self):
        with _which_only("codex"):
            code, out, err = self.init()
        self.assertEqual(code, 0, err)
        self.assertFalse((self.project / ".claude").exists())
        self.assertTrue((self.project / ".agents/skills/change-review/SKILL.md").is_file())
        self.assertIn(CODEX_NEXT, out)
        self.assertNotIn(CLAUDE_NEXT, out)
