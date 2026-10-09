import os

from engkit.validator import validate, validate_name
from tests.helpers import REPO, TempDirTest, skill_text


def errors(result):
    return [i.format() for i in result.issues if i.level == "error"]


class ValidatorTest(TempDirTest):
    def test_valid_skill(self):
        root = self.make_toolkit({"good-skill": skill_text("good-skill")})
        self.assertEqual(errors(validate(root)), [])

    def test_name_mismatch(self):
        root = self.make_toolkit({"dir-name": skill_text("other-name")})
        self.assertTrue(any("does not match directory" in e for e in errors(validate(root))))

    def test_invalid_names(self):
        for i, bad in enumerate(
            ("Upper", "under_score", "-lead", "trail-", "double--hyphen", "a" * 65)
        ):
            with self.subTest(bad=bad):
                root = self.make_toolkit({bad: skill_text(bad)}, name=f"tk{i}")
                errs = errors(validate(root))
                self.assertTrue(errs, bad)
                self.assertIn(str(root / "skills" / bad), "\n".join(errs))

    def test_trailing_newline_in_name_is_rejected(self):
        self.assertIsNotNone(validate_name("demo\n"))
        root = self.make_toolkit({"demo": skill_text("demo")})
        self.assertTrue(any("invalid skill name" in e for e in errors(validate(root, "demo\n"))))

    def test_missing_and_malformed_frontmatter(self):
        root = self.make_toolkit({"nofm": "# no frontmatter\n", "badyaml": "---\nname: [x\n---\n"})
        errs = "\n".join(errors(validate(root)))
        self.assertIn("missing YAML frontmatter", errs)
        self.assertIn("malformed YAML", errs)

    def test_missing_description_and_too_long(self):
        root = self.make_toolkit(
            {
                "nodesc": "---\nname: nodesc\n---\n" + skill_text("x").split("---\n", 2)[2],
                "longdesc": skill_text("longdesc", "x" * 1025),
            }
        )
        errs = "\n".join(errors(validate(root)))
        self.assertIn("description must be a non-empty string", errs)
        self.assertIn("exceeds 1024", errs)

    def test_missing_sections(self):
        root = self.make_toolkit({"thin": "---\nname: thin\ndescription: d\n---\n## When to use\n"})
        self.assertTrue(any("missing required sections" in e for e in errors(validate(root))))

    def test_missing_and_escaping_references(self):
        extra = "\n## References\n[a](references/missing.md) [b](../other/SKILL.md) [c](https://example.test/x)\n"
        root = self.make_toolkit({"refs": skill_text("refs", extra=extra)})
        errs = "\n".join(errors(validate(root)))
        self.assertIn("missing reference 'references/missing.md'", errs)
        self.assertIn("escapes the skill directory", errs)
        self.assertNotIn("example.test", errs)

    def test_symlink_escaping_root(self):
        outside = self.tmp / "outside.md"
        outside.write_text("secret")
        root = self.make_toolkit({"linky": skill_text("linky")})
        os.symlink(outside, root / "skills" / "linky" / "leak.md")
        self.assertTrue(any("escapes toolkit root" in e for e in errors(validate(root))))

    def test_internal_symlink_is_error_because_install_refuses_it(self):
        root = self.make_toolkit({"linky": skill_text("linky")})
        os.symlink("SKILL.md", root / "skills" / "linky" / "alias.md")
        self.assertTrue(any("symlinks cannot be installed" in e for e in errors(validate(root))))

    def test_symlinked_skill_md_rejected(self):
        root = self.make_toolkit({"src": skill_text("src")})
        (root / "skills" / "linked").mkdir()
        os.symlink(root / "skills" / "src" / "SKILL.md", root / "skills" / "linked" / "SKILL.md")
        self.assertTrue(any("symlink" in e for e in errors(validate(root, "linked"))))

    def test_validate_single_and_unknown(self):
        root = self.make_toolkit({"one": skill_text("one"), "bad": "nope"})
        self.assertEqual(errors(validate(root, "one")), [])
        self.assertTrue(errors(validate(root, "bad")))
        self.assertTrue(any("unknown skill" in e for e in errors(validate(root, "absent"))))
        self.assertTrue(any("invalid skill name" in e for e in errors(validate(root, "../etc"))))

    def test_non_portable_key_is_warning(self):
        text = skill_text("warny").replace("description:", "custom: 1\ndescription:")
        root = self.make_toolkit({"warny": text})
        result = validate(root)
        self.assertEqual(errors(result), [])
        self.assertTrue(
            any(i.level == "warning" and "non-portable" in i.message for i in result.issues)
        )


class CanonicalSkillsTest(TempDirTest):
    EXPECTED = {
        "systematic-debugging",
        "change-review",
        "implementation-planning",
        "project-discovery",
        "stack-selection",
        "project-memory",
    }
    REMOVED_FEATURES = (
        "PROJECT_CONTEXT",
        ".engkit/generated",
        "engkit project",
        "engkit stack",
    )

    def test_repository_skills_are_valid(self):
        result = validate(REPO)
        self.assertEqual(errors(result), [])
        self.assertEqual({s.name for s in result.skills}, self.EXPECTED)

    def test_contract_phrases_in_every_skill(self):
        for skill_name in sorted(self.EXPECTED):
            text = (REPO / "skills" / skill_name / "SKILL.md").read_text()
            with self.subTest(skill=skill_name):
                for phrase in (
                    "## When to ask",
                    "verified fact",
                    "plausible hypothesis",
                    "untested assumption",
                ):
                    self.assertIn(phrase, text)
                if skill_name != "project-memory":
                    self.assertIn(".engkit/memory/INDEX.md", text)

    def test_skills_are_short_and_free_of_removed_features(self):
        for skill_name in sorted(self.EXPECTED):
            text = (REPO / "skills" / skill_name / "SKILL.md").read_text()
            with self.subTest(skill=skill_name):
                self.assertLessEqual(len(text.splitlines()), 120)
                for phrase in self.REMOVED_FEATURES:
                    self.assertNotIn(phrase, text)
