import re
import unittest

from tests.helpers import REPO

SKILL_DIRS = {"debugging": "systematic-debugging", "review": "code-review", "planning": "implementation-planning",
              "discovery": "project-discovery", "selection": "stack-selection"}
SECTIONS = ("## Prompt", "## Fixture", "## Rubric", "## Critical expected findings", "## Disallowed hallucinations",
            "## Pass threshold")


class EvalStructureTest(unittest.TestCase):
    def cases(self):
        return sorted(p.parent for p in (REPO / "evals").glob("*/*/case.md"))

    def test_at_least_ten_cases_two_per_skill(self):
        cases = self.cases()
        self.assertGreaterEqual(len(cases), 10)
        for d in SKILL_DIRS:
            self.assertGreaterEqual(len([c for c in cases if c.parent.name == d]), 2, d)

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
                self.assertIsNone(re.search(r"(?i)(api[_-]?key|secret)\s*[:=]\s*['\"]?[A-Za-z0-9]{20,}", p.read_text(errors="ignore")), p)
