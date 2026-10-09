import os

from engkit.catalog import discover, split_frontmatter, FrontmatterError
from tests.helpers import TempDirTest, skill_text


class CatalogTest(TempDirTest):
    def test_deterministic_order_and_descriptions(self):
        root = self.make_toolkit({n: skill_text(n, f"Desc {n}.") for n in ("zeta", "alpha", "mid-one")})
        first = discover(root)
        second = discover(root)
        self.assertEqual([s.name for s in first.skills], ["alpha", "mid-one", "zeta"])
        self.assertEqual([s.name for s in first.skills], [s.name for s in second.skills])
        self.assertEqual(first.skills[0].description, "Desc alpha.")
        self.assertTrue(first.ok)

    def test_empty_directory(self):
        result = discover(self.make_toolkit())
        self.assertEqual(result.skills, [])
        self.assertTrue(result.ok)

    def test_missing_skills_directory(self):
        result = discover(self.tmp)
        self.assertFalse(result.ok)
        self.assertIn("skills directory not found", result.issues[0].message)

    def test_hidden_entries_and_files_ignored(self):
        root = self.make_toolkit({"good": skill_text("good")})
        (root / "skills" / ".hidden").mkdir()
        (root / "skills" / "README.md").write_text("x")
        result = discover(root)
        self.assertEqual([s.name for s in result.skills], ["good"])
        self.assertTrue(result.ok)

    def test_missing_skill_md(self):
        root = self.make_toolkit()
        (root / "skills" / "empty").mkdir()
        result = discover(root)
        self.assertFalse(result.ok)
        self.assertIn("missing SKILL.md", result.issues[0].format())
        self.assertIn(str(root / "skills" / "empty" / "SKILL.md"), result.issues[0].format())

    def test_duplicate_names_rejected(self):
        root = self.make_toolkit({"one": skill_text("same"), "two": skill_text("same")})
        result = discover(root)
        self.assertFalse(result.ok)
        self.assertEqual(result.skills, [])
        self.assertEqual(len([i for i in result.issues if "duplicate skill name" in i.message]), 2)

    def test_symlinked_skill_dir_rejected(self):
        root = self.make_toolkit({"real": skill_text("real")})
        os.symlink(root / "skills" / "real", root / "skills" / "alias")
        result = discover(root)
        self.assertFalse(result.ok)
        self.assertTrue(any("symlink" in i.message for i in result.issues))


class FrontmatterTest(TempDirTest):
    def test_parses_mapping(self):
        meta, body = split_frontmatter("---\nname: a\ndescription: b\n---\nbody\n")
        self.assertEqual(meta, {"name": "a", "description": "b"})
        self.assertEqual(body, "body\n")

    def test_errors(self):
        for text, fragment in [
            ("no frontmatter", "missing YAML frontmatter"),
            ("---\nname: a\n", "unterminated"),
            ("---\nname: [a\n---\n", "malformed YAML at frontmatter line"),
            ("---\n- a\n---\n", "must be a YAML mapping"),
        ]:
            with self.subTest(text=text):
                with self.assertRaises(FrontmatterError) as ctx:
                    split_frontmatter(text)
                self.assertIn(fragment, str(ctx.exception))
