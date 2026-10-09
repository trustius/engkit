import re
import unittest

from tests.helpers import REPO

SKILL_DIRS = {
    "debugging": "bug-investigate",
    "review": "change-review",
    "planning": "change-plan",
    "discovery": "engineering-onboard",
    "selection": "stack-select",
    "memory": "memory-save",
}
SECTIONS = (
    "## Prompt",
    "## Fixture",
    "## Rubric",
    "## Critical expected findings",
    "## Disallowed hallucinations",
    "## Pass threshold",
)


class EvalStructureTest(unittest.TestCase):
    def cases(self):
        return sorted(p.parent for p in (REPO / "evals").glob("*/*/case.md"))

    def test_at_least_ten_cases_two_per_skill(self):
        cases = self.cases()
        self.assertGreaterEqual(len(cases), 10)
        for d in SKILL_DIRS:
            self.assertGreaterEqual(len([c for c in cases if c.parent.name == d]), 2, d)

    def test_rules_area_has_four_cases_naming_their_command(self):
        cases = [c for c in self.cases() if c.parent.name == "rules"]
        self.assertGreaterEqual(len(cases), 4)
        for case in cases:
            text = (case / "case.md").read_text()
            prompt = text.split("## Prompt", 1)[1].split("\n## ", 1)[0]
            with self.subTest(case=case.name):
                self.assertRegex(prompt, r"/(bug-investigate|change-plan|change-review)")

    def test_case_sections(self):
        for case in self.cases():
            text = (case / "case.md").read_text()
            with self.subTest(case=case.name):
                for section in SECTIONS:
                    self.assertIn(section, text)

    def test_status_table_has_no_invented_results(self):
        readme = (REPO / "evals" / "README.md").read_text()
        for case in self.cases():
            cid = f"{case.parent.name}/{case.name}"
            row = next((line for line in readme.splitlines() if line.startswith(f"| {cid} ")), None)
            self.assertIsNotNone(row, cid)
            cells = [c.strip() for c in row.strip("|").split("|")][2:]
            self.assertTrue(cells and all(c in ("pass", "fail", "not-run") for c in cells), row)

    def test_fixtures_are_not_executable(self):
        import os

        for p in (REPO / "evals").rglob("*"):
            if p.is_file():
                self.assertFalse(os.access(p, os.X_OK), p)
                self.assertIsNone(
                    re.search(
                        r"(?i)(api[_-]?key|secret)\s*[:=]\s*['\"]?[A-Za-z0-9]{20,}",
                        p.read_text(errors="ignore"),
                    ),
                    p,
                )


class TriggerEvalTest(unittest.TestCase):
    def prompts(self, text, heading):
        body = text.split(heading, 1)[1].split("\n## ", 1)[0]
        return re.findall(r"(?m)^\d+\. \S", body)

    def test_every_skill_has_five_plus_five_trigger_prompts(self):
        for skill_name in SKILL_DIRS.values():
            path = REPO / "evals" / "triggers" / f"{skill_name}.md"
            with self.subTest(skill=skill_name):
                text = path.read_text()
                self.assertEqual(text.count("\n## "), 2)
                self.assertEqual(len(self.prompts(text, "## Should trigger")), 5)
                self.assertEqual(len(self.prompts(text, "## Should not trigger")), 5)

    def test_trigger_results_have_no_invented_outcomes(self):
        readme = (REPO / "evals" / "triggers" / "README.md").read_text()
        rows = [
            line
            for line in readme.splitlines()
            if line.startswith("| ") and not line.startswith(("| Skill", "|---"))
        ]
        self.assertEqual(len(rows), len(SKILL_DIRS))
        for row in rows:
            cells = [cell.strip() for cell in row.strip("|").split("|")][1:]
            self.assertTrue(all(cell in ("pass", "fail", "not-run") for cell in cells), row)
