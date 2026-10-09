from __future__ import annotations

import os

from engkit import memory
from tests.helpers import TempDirTest, snapshot

ENTRY = """---
name: retry-policy
type: decision
status: verified
updated: 2026-10-09
sources: [src/retry.py]
---
Retries use fixed backoff because the upstream rate limits per second.
"""
INDEX = "# Project memory\n\n- [Retry policy](retry-policy.md) — decision — Fixed backoff\n"


class MemoryTest(TempDirTest):
    def good_project(self, entry=ENTRY, index=INDEX, name="project"):
        files = {
            ".engkit/memory/.gitignore": "*\n",
            ".engkit/memory/INDEX.md": index,
            ".engkit/memory/retry-policy.md": entry,
        }
        return self.make_project(name, files)

    def messages(self, root):
        return [f"{i.level}:{i.path.name}:{i.message}" for i in memory.validate(root)]

    def assert_error(self, root, fragment):
        found = [m for m in self.messages(root) if fragment in m and m.startswith("error")]
        self.assertTrue(found, self.messages(root))

    def test_init_creates_layout(self):
        root = self.make_project()
        result = memory.init(root)
        self.assertEqual(len(result.created), 2)
        self.assertEqual(result.existing, [])
        self.assertEqual((root / ".engkit/memory/.gitignore").read_text(), "*\n")
        self.assertTrue((root / ".engkit/memory/INDEX.md").is_file())
        self.assertFalse((root / "CLAUDE.md").exists())
        self.assertEqual(memory.validate(root), [])

    def test_init_idempotent_and_never_overwrites(self):
        root = self.make_project()
        memory.init(root)
        (root / ".engkit/memory/INDEX.md").write_text("custom\n")
        (root / ".engkit/memory/.gitignore").write_text("mine\n")
        result = memory.init(root)
        self.assertEqual(result.created, [])
        self.assertEqual(len(result.existing), 2)
        self.assertEqual((root / ".engkit/memory/INDEX.md").read_text(), "custom\n")
        self.assertEqual((root / ".engkit/memory/.gitignore").read_text(), "mine\n")

    def test_init_refuses_symlinked_dirs(self):
        outside = self.make_project("outside")
        for link_rel, parts in (
            (".engkit", ()),
            (".engkit/memory", (".engkit",)),
        ):
            root = self.make_project(f"p{len(parts)}")
            parent = root.joinpath(*parts)
            parent.mkdir(exist_ok=True)
            os.symlink(outside, root / link_rel)
            with self.assertRaises(memory.fsutil.UnsafePathError):
                memory.init(root)
        self.assertEqual(snapshot(outside), {})

    def test_validate_good(self):
        self.assertEqual(memory.validate(self.good_project()), [])
        self.assertEqual(
            memory.status(self.good_project(name="again")), ("info", "project memory: 1 entries ok")
        )

    def test_missing_dir(self):
        root = self.make_project()
        issues = memory.validate(root)
        self.assertEqual(len(issues), 1)
        self.assertIn("engkit memory init", issues[0].message)
        self.assertEqual(memory.status(root)[0], "info")

    def test_bad_frontmatter_and_yaml(self):
        self.assert_error(self.good_project("no front\n"), "frontmatter")
        self.assert_error(self.good_project("---\nname: [oops\n---\n", name="q"), "YAML")

    def test_field_errors(self):
        cases = {
            "name: retry-policy": ("name: other-name", "must equal the file stem"),
            "type: decision": ("type: opinion", "type must be"),
            "status: verified": ("status: sure", "status must be"),
            "updated: 2026-10-09": ("updated: yesterday", "ISO date"),
            "sources: [src/retry.py]": ("sources: src/retry.py", "list of strings"),
        }
        for index, (old, (new, fragment)) in enumerate(cases.items()):
            root = self.good_project(ENTRY.replace(old, new), name=f"case{index}")
            self.assert_error(root, fragment)

    def test_date_string_and_empty_sources_accepted(self):
        entry = ENTRY.replace("2026-10-09", "'2026-10-09'").replace("[src/retry.py]", "[]")
        self.assertEqual(memory.validate(self.good_project(entry)), [])

    def test_index_errors(self):
        self.assert_error(self.good_project(index="# Project memory\n"), "not listed")
        dangling = INDEX + "- [Gone](gone.md) — gotcha — Missing\n"
        self.assert_error(self.good_project(index=dangling, name="a"), "does not exist")
        duplicate = INDEX + INDEX.splitlines()[2] + "\n"
        self.assert_error(self.good_project(index=duplicate, name="b"), "more than once")
        mismatch = INDEX.replace("— decision —", "— gotcha —")
        self.assert_error(self.good_project(index=mismatch, name="c"), "differs from entry type")

    def test_odd_index_line_warns(self):
        root = self.good_project(index=INDEX + "random text\n")
        levels = [i.level for i in memory.validate(root)]
        self.assertEqual(levels, ["warning"])

    def test_size_limits(self):
        long_index = INDEX + "\n" * 150
        self.assert_error(self.good_project(index=long_index), "INDEX.md exceeds")
        long_entry = ENTRY + "line\n" * 60
        self.assert_error(self.good_project(long_entry, name="b"), "entry exceeds")

    def test_symlinked_entry(self):
        root = self.good_project()
        target = self.tmp / "elsewhere.md"
        target.write_text(ENTRY)
        os.symlink(target, root / ".engkit/memory/other.md")
        self.assert_error(root, "regular file")

    def test_secret_warning_hides_value(self):
        secret = "AKIAABCDEFGHIJKLMNOP"
        entry = ENTRY + f"aws {secret}\npassword: hunter2hunter2\npassword: <your-password>\n"
        root = self.good_project(entry)
        issues = memory.validate(root)
        self.assertEqual([i.level for i in issues], ["warning", "warning"])
        text = " ".join(i.format() for i in issues)
        self.assertNotIn(secret, text)
        self.assertNotIn("hunter2", text)
        self.assertIn("retry-policy.md", text)
        self.assertIn("line 9", text)
        self.assertEqual(memory.status(root), ("warning", "project memory: 0 errors, 2 warnings"))

    def test_validate_read_only(self):
        root = self.good_project(ENTRY + "token: abcdef123456\n", index="bad\n")
        before = snapshot(root)
        memory.validate(root)
        memory.status(root)
        self.assertEqual(snapshot(root), before)
