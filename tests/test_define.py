from engkit import define
from engkit.errors import EXIT_CONFLICT, EXIT_FAILURE, EXIT_OK
from tests import fixtures
from tests.helpers import REPO, TempDirTest, snapshot

STACK = """schema_version: 1
kind: stack
id: widget-service
description: synthetic
project: {mode: new, constraints: {team_size: 2}}
components:
  - id: service
    root: .
    stack: {languages: [widgetlang]}
    commands:
      test: {argv: [widgetc, test], status: documented}
    packs: [{id: acme-widget, version: 2.1.0}]
"""


class DefineTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.project = self.make_project("svc", fixtures.custom_pack_files())
        self.stack = self.tmp / "widget.yaml"
        self.stack.write_text(STACK)

    def test_stack_validate_with_project_pack(self):
        outcome = define.validate_stack(self.stack, self.project, REPO)
        self.assertEqual((outcome.status, outcome.exit_code), ("valid", EXIT_OK), [d.format() for d in outcome.diagnostics])
        # Without the project registry the custom pack is unknown.
        outcome = define.validate_stack(self.stack, self.make_project("empty"), REPO)
        self.assertEqual(outcome.exit_code, EXIT_FAILURE)
        self.assertIn("missing-pack", {d.code for d in outcome.diagnostics})

    def test_stack_validate_rejects_bad_definition(self):
        self.stack.write_text(STACK.replace("root: .", "root: ../escape"))
        outcome = define.validate_stack(self.stack, self.project, REPO)
        self.assertEqual(outcome.status, "invalid")
        self.assertIn("unsafe-path", {d.code for d in outcome.diagnostics})

    def test_define_new_project_and_idempotency(self):
        dry_before = snapshot(self.project)
        self.assertEqual(define.define(self.stack, self.project, REPO, dry_run=True).status, "dry-run")
        self.assertEqual(snapshot(self.project), dry_before)
        outcome = define.define(self.stack, self.project, REPO)
        self.assertEqual((outcome.status, outcome.exit_code), ("defined", EXIT_OK))
        text = (self.project / ".engkit/project.yaml").read_text()
        self.assertIn("mode: new", text)
        self.assertIn("name: svc", text)
        self.assertEqual(define.define(self.stack, self.project, REPO).status, "already defined")
        before = snapshot(self.project)
        self.stack.write_text(STACK.replace("team_size: 2", "team_size: 3"))
        outcome = define.define(self.stack, self.project, REPO)
        self.assertEqual((outcome.status, outcome.exit_code), ("conflict", EXIT_CONFLICT))
        self.assertEqual(snapshot(self.project), before)

    def test_define_existing_project_reports_contradictions(self):
        project = self.make_project("goproj", fixtures.GO_CLI)
        stack = self.tmp / "s.yaml"
        stack.write_text("schema_version: 1\nkind: stack\nid: s\ncomponents:\n  - id: root\n    root: .\n"
                         "    stack: {languages: [c]}\n")
        outcome = define.define(stack, project, REPO)
        self.assertEqual(outcome.status, "defined")
        self.assertIn("contradiction", {d.code for d in outcome.diagnostics})
        self.assertIn("mode: existing", (project / ".engkit/project.yaml").read_text())
        self.assertEqual((project / "go.mod").read_text(), fixtures.GO_CLI["go.mod"])

    def test_unknown_stack_project_accepts_manual_definition(self):
        project = self.make_project("odd", fixtures.UNKNOWN)
        stack = self.tmp / "odd.yaml"
        stack.write_text("schema_version: 1\nkind: stack\nid: odd\ncomponents:\n  - id: main\n    root: .\n"
                         "    stack: {languages: [xyz-lang]}\n    commands: {test: {argv: [xyzc, check], status: documented}}\n")
        self.assertEqual(define.define(stack, project, REPO).status, "defined")
        from engkit.resolution import inspect_project
        state = inspect_project(project, REPO)
        comps = state.resolved.profile["components"]
        self.assertEqual([c["id"] for c in comps], ["main"])
        self.assertEqual(comps[0]["commands"]["test"]["argv"], ["xyzc", "check"])
        self.assertIn("compatibility-unknown", {d.code for d in state.pack_resolution.diagnostics})

    def test_shipped_example_stack_is_valid(self):
        outcome = define.validate_stack(REPO / "stacks" / "example-service.yaml", self.make_project("x"), REPO)
        self.assertEqual(outcome.status, "valid", [d.format() for d in outcome.diagnostics])
