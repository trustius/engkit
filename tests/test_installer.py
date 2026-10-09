import os
import threading
from pathlib import Path
from unittest import mock

from engkit import fsutil, installer
from engkit.errors import EXIT_BUSY, EXIT_CONFLICT, EXIT_IO, EXIT_OK
from tests.helpers import TempDirTest, skill_text, snapshot


class InstallerTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.toolkit = self.make_toolkit(
            {"demo": skill_text("demo", extra="\n[r](references/deep/notes.md)\n")}
        )
        skill = self.toolkit / "skills" / "demo"
        (skill / "references" / "deep").mkdir(parents=True)
        (skill / "references" / "deep" / "notes.md").write_text("nested reference\n")
        (skill / "scripts").mkdir()
        marker = self.tmp / "EXECUTED"
        (skill / "scripts" / "run.sh").write_text(f"#!/bin/sh\ntouch {marker}\n")
        os.chmod(skill / "scripts" / "run.sh", 0o755)
        self.marker = marker
        self.project = self.make_project()

    def install(self, target="claude", **kw):
        kw.setdefault("project_dir", self.project)
        return installer.install(self.toolkit, "demo", target, **kw)

    def assert_copy(self, dest: Path):
        self.assertEqual(
            fsutil.tree_snapshot(dest), fsutil.tree_snapshot(self.toolkit / "skills" / "demo")
        )

    def test_project_install_both_targets_copies_nested_files(self):
        results = self.install("all")
        self.assertEqual(
            [(r.platform, r.status) for r in results],
            [("claude", "installed"), ("codex", "installed")],
        )
        self.assert_copy(self.project / ".claude/skills/demo")
        self.assert_copy(self.project / ".agents/skills/demo")
        self.assertTrue(os.access(self.project / ".claude/skills/demo/scripts/run.sh", os.X_OK))
        self.assertFalse(self.marker.exists(), "installer must never execute bundled scripts")

    def test_global_install_uses_home(self):
        results = installer.install(self.toolkit, "demo", "all", scope="user", home_dir=self.home)
        self.assertTrue(all(r.status == "installed" for r in results))
        self.assert_copy(self.home / ".claude/skills/demo")
        self.assert_copy(self.home / ".codex/skills/demo")
        self.assertFalse((self.project / ".claude").exists())

    def test_global_defaults_to_home_env(self):
        results = installer.install(self.toolkit, "demo", "codex", scope="user")
        self.assertEqual(results[0].destination, self.home / ".codex/skills/demo")

    def test_repeat_install_is_idempotent(self):
        self.install()
        before = snapshot(self.project)
        result = self.install()[0]
        self.assertEqual((result.status, result.exit_code), ("already installed", EXIT_OK))
        self.assertEqual(snapshot(self.project), before)

    def test_conflict_leaves_existing_untouched(self):
        dest = self.project / ".claude/skills/demo"
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("user's own version\n")
        before = snapshot(self.project)
        result = self.install()[0]
        self.assertEqual((result.status, result.exit_code), ("conflict", EXIT_CONFLICT))
        self.assertEqual(snapshot(self.project), before)

    def test_all_reports_per_target(self):
        dest = self.project / ".agents/skills/demo"
        dest.mkdir(parents=True)
        (dest / "other.txt").write_text("x")
        results = self.install("all")
        self.assertEqual([r.status for r in results], ["installed", "conflict"])

    def test_invalid_source_installs_nothing(self):
        (self.toolkit / "skills" / "demo" / "SKILL.md").write_text("broken")
        result = self.install()[0]
        self.assertEqual(result.status, "error")
        self.assertFalse((self.project / ".claude").exists())

    def test_failed_copy_leaves_no_partial_directory(self):
        def boom(stage, target):
            if stage == "staged":
                raise OSError("simulated disk full")

        with mock.patch.object(installer, "fault_hook", boom):
            result = self.install()[0]
        self.assertEqual((result.status, result.exit_code), ("error", EXIT_IO))
        self.assertEqual(os.listdir(self.project / ".claude/skills"), [])

    def test_permission_failure(self):
        skills = self.project / ".claude/skills"
        skills.mkdir(parents=True)
        os.chmod(skills, 0o555)
        try:
            result = self.install()[0]
        finally:
            os.chmod(skills, 0o755)
        self.assertEqual(result.status, "error")
        self.assertEqual(os.listdir(skills), [])

    def test_symlinked_destination_parent_rejected(self):
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        os.symlink(elsewhere, self.project / ".claude")
        result = self.install()[0]
        self.assertEqual(result.status, "error")
        self.assertIn("symlink", result.detail)
        self.assertEqual(os.listdir(elsewhere), [], "no write may escape the resolved root")

    def test_symlinked_skills_dir_rejected(self):
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        (self.project / ".agents").mkdir()
        os.symlink(elsewhere, self.project / ".agents/skills")
        result = self.install("codex")[0]
        self.assertEqual(result.status, "error")
        self.assertEqual(os.listdir(elsewhere), [])

    def test_symlinked_destination_is_conflict(self):
        (self.project / ".claude/skills").mkdir(parents=True)
        os.symlink(self.toolkit / "skills" / "demo", self.project / ".claude/skills/demo")
        result = self.install()[0]
        self.assertEqual(result.status, "conflict")
        self.assertTrue((self.project / ".claude/skills/demo").is_symlink())

    def test_destination_created_just_before_publication(self):
        def race(stage, target):
            if stage == "before_publish":
                target.mkdir()
                (target / "SKILL.md").write_text("other writer\n")

        for native in (True, False):
            with self.subTest(native=native):
                project = self.make_project(f"race-{native}")
                with mock.patch.object(installer, "fault_hook", race):
                    result = self.install(project_dir=project, allow_native_noreplace=native)[0]
                self.assertEqual(result.status, "conflict")
                dest = project / ".claude/skills/demo"
                self.assertEqual((dest / "SKILL.md").read_text(), "other writer\n")
                self.assertEqual(
                    sorted(os.listdir(dest.parent)), ["demo"], "staging must be cleaned"
                )

    def test_identical_destination_appearing_before_publication(self):
        source = self.toolkit / "skills" / "demo"

        def race(stage, target):
            if stage == "before_publish":
                fsutil.copy_tree_regular(source, target)

        with mock.patch.object(installer, "fault_hook", race):
            result = self.install()[0]
        self.assertEqual(result.status, "already installed")

    def test_empty_reservation_reports_busy(self):
        (self.project / ".claude/skills/demo").mkdir(parents=True)
        result = self.install()[0]
        self.assertEqual((result.status, result.exit_code), ("busy", EXIT_BUSY))

    def test_reservation_fallback_installs(self):
        result = self.install(allow_native_noreplace=False)[0]
        self.assertEqual(result.status, "installed")
        self.assert_copy(self.project / ".claude/skills/demo")

    def test_native_noreplace_refuses_existing(self):
        a, b = self.tmp / "a", self.tmp / "b"
        a.mkdir()
        b.mkdir()
        try:
            with self.assertRaises(FileExistsError):
                fsutil.rename_noreplace(a, b)
        except fsutil.NoReplaceUnsupported:
            self.skipTest("no native no-replace rename on this platform")
        self.assertTrue(a.exists() and b.exists())

    def _concurrent(self, sources: list[Path], native: bool) -> list:
        barrier = threading.Barrier(len(sources))
        results = [None] * len(sources)
        project = self.make_project(f"conc-{native}-{len(os.listdir(self.tmp))}")

        def hook(stage, target):
            if stage == "before_publish":
                barrier.wait(timeout=10)

        def worker(i, toolkit):
            results[i] = installer.install(
                toolkit, "demo", "claude", project_dir=project, allow_native_noreplace=native
            )[0]

        with mock.patch.object(installer, "fault_hook", hook):
            threads = [threading.Thread(target=worker, args=(i, s)) for i, s in enumerate(sources)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(30)
        return results, project

    def test_concurrent_identical_installs(self):
        for native in (True, False):
            with self.subTest(native=native):
                results, project = self._concurrent([self.toolkit] * 4, native)
                statuses = sorted(result.status for result in results)
                self.assertEqual(statuses.count("installed"), 1, statuses)
                allowed = _loser_statuses(native, "already installed")
                self.assertTrue(all(status in allowed for status in statuses), statuses)
                self.assert_copy(project / ".claude/skills/demo")
                self.assertEqual(os.listdir(project / ".claude/skills"), ["demo"])

    def test_concurrent_differing_installs(self):
        other = self.make_toolkit(
            {"demo": skill_text("demo", "A different description.")}, name="toolkit2"
        )
        for native in (True, False):
            with self.subTest(native=native):
                results, project = self._concurrent([self.toolkit, other], native)
                statuses = sorted(result.status for result in results)
                self.assertEqual(statuses.count("installed"), 1, statuses)
                losers = [status for status in statuses if status != "installed"]
                self.assertIn(losers[0], _loser_statuses(native, "conflict"), statuses)
                winner = [
                    s
                    for r, s in zip(results, [self.toolkit, other], strict=True)
                    if r.status == "installed"
                ][0]
                self.assertEqual(
                    fsutil.tree_snapshot(project / ".claude/skills/demo"),
                    fsutil.tree_snapshot(winner / "skills" / "demo"),
                )

    def test_status_of(self):
        source = self.toolkit / "skills" / "demo"
        dest = self.project / ".claude/skills/demo"
        self.assertEqual(installer.status_of(source, dest), "missing")
        self.install()
        self.assertEqual(installer.status_of(source, dest), "identical")
        (dest / "SKILL.md").write_text("changed")
        self.assertEqual(installer.status_of(source, dest), "differs")

    def test_tree_snapshot_propagates_unreadable_directory(self):
        source = self.toolkit / "skills" / "demo"
        locked = source / "references" / "deep"
        os.chmod(locked, 0o000)
        self.addCleanup(os.chmod, locked, 0o755)
        with self.assertRaises(OSError):
            fsutil.tree_snapshot(source)
        with self.assertRaises(OSError):
            fsutil.copy_tree_regular(source, self.tmp / "copy")

    def test_symlinked_skills_dir_with_identical_copy_is_refused(self):
        self.install()
        elsewhere = self.tmp / "elsewhere"
        (self.project / ".claude/skills").rename(elsewhere)
        os.symlink(elsewhere, self.project / ".claude/skills")
        result = self.install()[0]
        self.assertEqual(result.status, "error")
        self.assertIn("unsafe destination", result.detail)

    def test_status_of_unreadable_destination_is_unsafe(self):
        source = self.toolkit / "skills" / "demo"
        dest = self.project / ".claude/skills/demo"
        self.install()
        os.chmod(dest, 0o000)
        self.addCleanup(os.chmod, dest, 0o755)
        self.assertEqual(installer.status_of(source, dest), "unsafe")


def _loser_statuses(native: bool, expected: str) -> set[str]:
    # The reservation protocol exposes an empty directory while the winner publishes,
    # and a loser that inspects it then must report the retryable "busy" (ADR 0002).
    if native:
        return {"installed", expected}
    return {"installed", expected, "busy"}
