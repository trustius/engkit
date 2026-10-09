import json
import os
from pathlib import Path
from unittest import mock

from engkit import generation
from engkit.errors import EXIT_BUSY, EXIT_CONFLICT, EXIT_FAILURE, EXIT_IO, EXIT_OK
from tests import fixtures
from tests.helpers import REPO, TempDirTest, snapshot


class Interrupt(BaseException):
    """Simulates a process being killed: not caught by the rollback handler."""


def fail_at(stage, exc=OSError):
    def hook(s):
        if s == stage:
            raise exc(f"injected failure at {s}")
    return hook


class GenerationTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.project = self.make_project("mono", fixtures.MONOREPO)
        self.gen = self.project / ".engkit" / "generated"

    def generate(self, targets=("claude", "codex"), project=None, **kw):
        return generation.generate(project or self.project, REPO, list(targets), **kw)

    def outside_engkit(self, root=None):
        return {k: v for k, v in snapshot(root or self.project).items() if not k.startswith(".engkit")}

    def test_initial_generation_and_manifest_consistency(self):
        before = self.outside_engkit()
        report = self.generate()
        self.assertEqual((report.status, report.exit_code), ("created", EXIT_OK))
        self.assertEqual(self.outside_engkit(), before, "unrelated project files are preserved")
        manifest = json.loads((self.gen / "manifest.json").read_text())
        files = {p: h for p, h in generation.tree_snapshot(self.gen).items()}
        self.assertEqual({p: h for p, h in files.items() if p != "manifest.json"},
                         {p: h for p, h in manifest["outputs"].items() if p != "manifest.json"})
        self.assertIn("platform/claude.md", files)
        self.assertIn("components/apps-web.md", files)
        self.assertIn("tools/cli/go.mod", manifest["inputs"])
        bundle_text = "".join(p.read_text() for p in self.gen.rglob("*") if p.is_file())
        self.assertNotIn(str(self.tmp), bundle_text, "no absolute machine paths in output")
        self.assertEqual(sorted(os.listdir(self.project / ".engkit")), ["generated"], "no leftover lock/staging/journal")
        for name in ("CLAUDE.md", "AGENTS.md"):
            self.assertFalse((self.project / name).exists())

    def test_component_context_is_scoped(self):
        self.generate()
        cli = (self.gen / "components" / "tools-cli.md").read_text()
        self.assertIn("`go test ./...`", cli)
        self.assertIn("cwd `tools/cli`", cli)
        self.assertNotIn("cargo", cli)
        web = (self.gen / "components" / "apps-web.md").read_text()
        self.assertIn("ambiguous", web)
        index = (self.gen / "PROJECT_CONTEXT.md").read_text()
        self.assertIn("| `libs-core` | `libs/core` |", index)

    def test_deterministic_bytes(self):
        a = self.make_project("a/mono", fixtures.MONOREPO)
        b = self.make_project("b/mono", fixtures.MONOREPO)
        self.generate(project=a)
        self.generate(project=b)
        self.assertEqual(snapshot(a / ".engkit/generated"), snapshot(b / ".engkit/generated"))

    def test_unchanged_is_noop(self):
        self.generate()
        before = snapshot(self.project)
        report = self.generate()
        self.assertEqual((report.status, report.exit_code), ("unchanged", EXIT_OK))
        self.assertEqual(snapshot(self.project), before)

    def test_profile_change_conflicts_until_replaced(self):
        self.generate()
        before = snapshot(self.project)
        (self.project / ".engkit" / "project.yaml").write_text(
            "schema_version: 1\nproject: {name: mono}\ncomponents:\n"
            "  - id: apps-web\n    root: apps/web\n    stack: {package_managers: [pnpm]}\n")
        report = self.generate()
        self.assertEqual((report.status, report.exit_code), ("conflict", EXIT_CONFLICT))
        self.assertIn("--replace-generated", "\n".join(report.lines))
        self.assertEqual({k: v for k, v in snapshot(self.project).items() if k != ".engkit/project.yaml"}, before)
        report = self.generate(replace=True)
        self.assertEqual(report.status, "replaced")
        web = (self.gen / "components" / "apps-web.md").read_text()
        self.assertIn("`pnpm run test`", web)
        backup = self.project / report.data["backup"]
        self.assertEqual(snapshot(backup), {k[len(".engkit/generated/"):]: v for k, v in before.items()
                                            if k.startswith(".engkit/generated/")})

    def test_user_edit_conflicts_and_replace_preserves_unrecognized(self):
        self.generate()
        ctx = self.gen / "PROJECT_CONTEXT.md"
        ctx.write_text(ctx.read_text() + "\nmy edit\n")
        (self.gen / "NOTES.md").write_text("user file\n")
        report = self.generate()
        self.assertEqual(report.status, "conflict")
        self.assertTrue(any("edited outputs: PROJECT_CONTEXT.md" in r for r in report.data["conflicts"]))
        dry = snapshot(self.project)
        self.assertEqual(self.generate(replace=True, dry_run=True).status, "dry-run")
        self.assertEqual(snapshot(self.project), dry, "dry-run replacement writes nothing")
        report = self.generate(replace=True)
        self.assertEqual(report.status, "replaced")
        self.assertEqual((self.gen / "NOTES.md").read_text(), "user file\n")
        self.assertNotIn("my edit", ctx.read_text())
        self.assertIn("my edit", (self.project / report.data["backup"] / "PROJECT_CONTEXT.md").read_text())
        self.assertEqual(self.generate().status, "unchanged")

    def test_replace_preserves_empty_user_directory(self):
        self.generate()
        (self.gen / "notes" / "drafts").mkdir(parents=True)
        ctx = self.gen / "PROJECT_CONTEXT.md"
        ctx.write_text(ctx.read_text() + "\nmy edit\n")
        report = self.generate(replace=True)
        self.assertEqual((report.status, report.exit_code), ("replaced", EXIT_OK))
        self.assertTrue((self.gen / "notes" / "drafts").is_dir())
        self.assertEqual(self.generate().status, "unchanged")

    def test_concurrent_edit_after_journal_is_conflict_not_blocked(self):
        self._prepare_replacement()

        def edit(stage):
            if stage == "after_journal":
                (self.gen / "LATE.md").write_text("written by the user mid-transaction\n")

        with mock.patch.object(generation, "fault_hook", edit):
            report = self.generate(replace=True)
        self.assertEqual((report.status, report.exit_code), ("conflict", EXIT_CONFLICT))
        self.assertEqual((self.gen / "LATE.md").read_text(), "written by the user mid-transaction\n")
        self.assertEqual((self.gen / "NOTES.md").read_text(), "keep me\n")
        self.assertFalse((self.project / generation.JOURNAL_REL).exists())
        self.assertFalse((self.project / generation.LOCK_REL).exists())
        self.assertFalse((self.project / ".engkit" / "staging").exists())
        self.assertEqual(self.generate(replace=True).status, "replaced", "later runs are not blocked")

    def test_missing_manifest_is_conflict(self):
        self.generate()
        (self.gen / "manifest.json").unlink()
        report = self.generate()
        self.assertEqual(report.status, "conflict")
        self.assertIn("manifest.json is missing", "\n".join(report.lines))
        self.assertEqual(self.generate(replace=True).status, "replaced")

    def test_target_change_is_input_change(self):
        self.generate()
        self.assertEqual(self.generate(targets=["claude"]).status, "conflict")
        report = self.generate(targets=["claude"], replace=True)
        self.assertEqual(report.status, "replaced")
        self.assertFalse((self.gen / "platform" / "codex.md").exists())
        self.assertTrue((self.project / report.data["backup"] / "platform" / "codex.md").exists())

    def test_dry_run_initial_writes_nothing(self):
        before = snapshot(self.project)
        report = self.generate(dry_run=True)
        self.assertEqual(report.status, "dry-run")
        self.assertEqual(snapshot(self.project), before)
        self.assertFalse((self.project / ".engkit").exists())

    def test_invalid_selection_blocks_before_writes(self):
        (self.project / ".engkit").mkdir()
        (self.project / ".engkit" / "project.yaml").write_text(
            "schema_version: 1\nproject: {name: mono}\ncomponents:\n  - id: x\n    root: tools/cli\n    packs: [{id: go, version: 9.9.9}]\n")
        before = snapshot(self.project)
        report = self.generate()
        self.assertEqual((report.status, report.exit_code), ("error", EXIT_FAILURE))
        self.assertIn("version-mismatch", "\n".join(report.lines))
        self.assertEqual(snapshot(self.project), before)

    def test_unknown_stack_project_generates_with_unresolved(self):
        project = self.make_project("odd", fixtures.UNKNOWN)
        self.assertEqual(self.generate(project=project).status, "created")
        text = (project / ".engkit/generated/components/root.md").read_text()
        self.assertIn("Stack is unknown", text)

    def test_custom_pack_generation(self):
        project = self.make_project("widget", {**fixtures.custom_pack_files(), "widget.build": "targets:\n  test: [x]\n"})
        report = self.generate(project=project)
        self.assertEqual(report.status, "created", report.lines)
        gen = project / ".engkit/generated"
        self.assertTrue((gen / "references/acme-widget/conventions.md").is_file())
        manifest = json.loads((gen / "manifest.json").read_text())
        self.assertEqual([(p["id"], p["version"], p["origin"]) for p in manifest["packs"]],
                         [("go", "1.0.0", "bundled"), ("acme-widget", "2.1.0", ".engkit/packs/acme-widget")])
        self.assertIn("`root` uses widget conventions from `acme-widget`", (gen / "components/root.md").read_text())

    # --- failure injection --------------------------------------------------------

    def _prepare_replacement(self):
        self.generate()
        (self.gen / "NOTES.md").write_text("keep me\n")
        (self.project / ".engkit" / "project.yaml").write_text(
            "schema_version: 1\nproject: {name: mono, constraints: {deployment: example}}\n")
        return snapshot(self.project)

    def test_handled_failures_restore_prior_bundle(self):
        for stage in ("after_staging", "backup", "after_journal", "after_aside", "after_swap"):
            with self.subTest(stage=stage):
                before = self._prepare_replacement()
                with mock.patch.object(generation, "fault_hook", fail_at(stage)):
                    report = self.generate(replace=True)
                self.assertNotEqual(report.exit_code, EXIT_OK)
                after = snapshot(self.project)
                gen_before = {k: v for k, v in before.items() if k.startswith(".engkit/generated")}
                gen_after = {k: v for k, v in after.items() if k.startswith(".engkit/generated")}
                self.assertEqual(gen_after, gen_before)
                self.assertFalse((self.project / generation.JOURNAL_REL).exists())
                self.assertFalse((self.project / generation.LOCK_REL).exists())
                self.assertFalse((self.project / ".engkit" / "staging").exists())
                self.assertEqual(generation.freshness(self.project, REPO)["status"], "stale")

    def test_backup_failure_leaves_bundle_untouched(self):
        before = self._prepare_replacement()
        with mock.patch.object(generation, "fault_hook", fail_at("backup")):
            report = self.generate(replace=True)
        self.assertEqual(report.exit_code, EXIT_IO)
        self.assertIn("backup failed", report.lines[0])
        self.assertEqual(os.listdir(self.project / ".engkit" / "backups"), [])
        self.assertEqual({k: v for k, v in snapshot(self.project).items() if k.startswith(".engkit/generated")},
                         {k: v for k, v in before.items() if k.startswith(".engkit/generated")})

    def test_first_generation_failure_restores_absence(self):
        with mock.patch.object(generation, "fault_hook", fail_at("after_swap")):
            report = self.generate()
        self.assertEqual(report.exit_code, EXIT_IO)
        self.assertFalse(self.gen.exists())
        self.assertFalse((self.project / generation.JOURNAL_REL).exists())

    def test_interrupted_replacement_blocks_and_recovers(self):
        for stage in ("after_journal", "after_aside", "after_swap"):
            with self.subTest(stage=stage):
                before = self._prepare_replacement()
                with mock.patch.object(generation, "fault_hook", fail_at(stage, Interrupt)):
                    with self.assertRaises(Interrupt):
                        self.generate(replace=True)
                self.assertTrue((self.project / generation.JOURNAL_REL).exists())
                self.assertEqual(generation.freshness(self.project, REPO)["status"], "incomplete")
                blocked = self.generate(replace=True)
                self.assertEqual(blocked.status, "blocked")
                # The killed process left its lock behind; it is never reclaimed automatically.
                lock = self.project / generation.LOCK_REL
                self.assertTrue(lock.exists())
                self.assertEqual(generation.recover(self.project).status, "busy")
                lock.unlink()  # the user's manual step after confirming no engkit process is running
                dry_before = snapshot(self.project)
                self.assertEqual(generation.recover(self.project, dry_run=True).status, "dry-run")
                self.assertEqual(snapshot(self.project), dry_before, "recovery dry-run writes nothing")
                report = generation.recover(self.project)
                self.assertEqual(report.status, "recovered", report.lines)
                self.assertEqual({k: v for k, v in snapshot(self.project).items() if k.startswith(".engkit/generated")},
                                 {k: v for k, v in before.items() if k.startswith(".engkit/generated")})
                self.assertFalse((self.project / generation.JOURNAL_REL).exists())
                backups = os.listdir(self.project / ".engkit" / "backups")
                self.assertTrue(backups, "backups are preserved")
                self.assertEqual(generation.recover(self.project).status, "nothing-to-recover")

    def test_interrupted_first_generation_recovers_to_absence(self):
        with mock.patch.object(generation, "fault_hook", fail_at("after_swap", Interrupt)):
            with self.assertRaises(Interrupt):
                self.generate()
        (self.project / generation.LOCK_REL).unlink()
        report = generation.recover(self.project)
        self.assertEqual(report.status, "recovered", report.lines)
        self.assertFalse(self.gen.exists())
        tx = json.loads(json.dumps(report.data))["transaction_id"]
        self.assertTrue((self.project / ".engkit" / "backups" / tx / "abandoned-generated").is_dir())

    def test_recovery_refuses_unexpected_edits(self):
        self._prepare_replacement()
        with mock.patch.object(generation, "fault_hook", fail_at("after_swap", Interrupt)):
            with self.assertRaises(Interrupt):
                self.generate(replace=True)
        (self.project / generation.LOCK_REL).unlink()
        (self.gen / "PROJECT_CONTEXT.md").write_text("edited after the crash\n")
        before = snapshot(self.project)
        report = generation.recover(self.project)
        self.assertEqual((report.status, report.exit_code), ("manual-recovery", EXIT_CONFLICT))
        self.assertEqual(snapshot(self.project), before)

    def test_recovery_rejects_tampered_journal(self):
        self._prepare_replacement()
        with mock.patch.object(generation, "fault_hook", fail_at("after_aside", Interrupt)):
            with self.assertRaises(Interrupt):
                self.generate(replace=True)
        (self.project / generation.LOCK_REL).unlink()
        journal_path = self.project / generation.JOURNAL_REL
        journal = json.loads(journal_path.read_text())
        journal["backup"] = "../../outside"
        journal_path.write_text(json.dumps(journal))
        before = snapshot(self.project)
        report = generation.recover(self.project)
        self.assertEqual(report.status, "manual-recovery")
        self.assertEqual(snapshot(self.project), before)

    def test_concurrent_generation_rejected(self):
        self.generate()
        (self.project / ".engkit" / "project.yaml").write_text("schema_version: 1\nproject: {name: other}\n")
        (self.project / generation.LOCK_REL).write_text(json.dumps({"pid": os.getpid(), "host": generation.socket.gethostname(),
                                                                    "transaction_id": "x"}))
        before = snapshot(self.project)
        report = self.generate(replace=True)
        self.assertEqual((report.status, report.exit_code), ("busy", EXIT_BUSY))
        self.assertEqual(snapshot(self.project), before)

    def test_stale_lock_is_described_not_reclaimed(self):
        (self.project / ".engkit").mkdir()
        (self.project / generation.LOCK_REL).write_text(json.dumps({"pid": 999999, "host": generation.socket.gethostname(),
                                                                    "transaction_id": "x"}))
        report = self.generate()
        self.assertEqual(report.status, "busy")
        self.assertIn("stale", report.lines[0])
        self.assertTrue((self.project / generation.LOCK_REL).exists())

    def test_symlinked_generated_dir_rejected(self):
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        (self.project / ".engkit").mkdir()
        (self.project / ".engkit" / "generated").symlink_to(elsewhere)
        report = self.generate()
        self.assertEqual(report.status, "error")
        self.assertEqual(os.listdir(elsewhere), [])

    # --- freshness ----------------------------------------------------------------

    def test_freshness_detects_new_removed_changed_and_edited(self):
        self.generate()
        self.assertEqual(generation.freshness(self.project, REPO)["status"], "fresh")
        (self.project / "libs" / "extra").mkdir()
        (self.project / "libs" / "extra" / "Cargo.toml").write_text("[package]\n")
        fresh = generation.freshness(self.project, REPO)
        self.assertEqual(fresh["status"], "stale")
        self.assertIn("new inputs: libs/extra/Cargo.toml", fresh["messages"])
        (self.project / "libs" / "extra" / "Cargo.toml").unlink()
        self.assertEqual(generation.freshness(self.project, REPO)["status"], "fresh")
        (self.project / "apps/web/pnpm-lock.yaml").unlink()
        fresh = generation.freshness(self.project, REPO)
        self.assertIn("removed inputs: apps/web/pnpm-lock.yaml", fresh["messages"])
        Path(self.project / "apps/web/pnpm-lock.yaml").write_text("lockfileVersion: 9\n")
        (self.gen / "components" / "tools-cli.md").unlink()
        fresh = generation.freshness(self.project, REPO)
        self.assertEqual((fresh["status"], fresh["missing"]), ("modified", ["components/tools-cli.md"]))
