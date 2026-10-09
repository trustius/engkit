import unittest
from pathlib import Path

from engkit import platforms


class PlatformTest(unittest.TestCase):
    def test_four_destinations(self):
        proj, home = Path("/p"), Path("/h")
        cases = {
            ("claude", "project", proj): "/p/.claude/skills/x",
            ("codex", "project", proj): "/p/.agents/skills/x",
            ("claude", "user", home): "/h/.claude/skills/x",
            ("codex", "user", home): "/h/.codex/skills/x",
        }
        for (pid, scope, root), expected in cases.items():
            with self.subTest(pid=pid, scope=scope):
                dest = platforms.destination(platforms.get(pid), scope, root)
                self.assertEqual(str(dest.skill_path("x")), expected)

    def test_expand_target(self):
        self.assertEqual([p.id for p in platforms.expand_target("all")], ["claude", "codex"])
        self.assertEqual([p.id for p in platforms.expand_target("codex")], ["codex"])
        with self.assertRaises(ValueError):
            platforms.expand_target("vim")
        with self.assertRaises(ValueError):
            platforms.destination(platforms.get("claude"), "system", Path("/"))
