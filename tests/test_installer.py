import os
import shutil
import threading
import unittest
from pathlib import Path
from unittest import mock

from engkit import fsutil, installer, lockfile
from engkit.errors import EXIT_BUSY, EXIT_CONFLICT, EXIT_IO, EXIT_OK
from tests.helpers import TempDirTest, skill_text, snapshot


class InstallerTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.toolkit = self.make_skills_dir(
            {"demo": skill_text("demo", extra="\n[r](references/deep/notes.md)\n")}
        )
        skill = self.toolkit / "demo"
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
        self.assertEqual(fsutil.tree_snapshot(dest), fsutil.tree_snapshot(self.toolkit / "demo"))

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
        self.assert_copy(self.home / ".agents/skills/demo")
        self.assertFalse((self.project / ".claude").exists())

    def test_global_defaults_to_home_env(self):
        results = installer.install(self.toolkit, "demo", "codex", scope="user")
        self.assertEqual(results[0].destination, self.home / ".agents/skills/demo")

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
        (self.toolkit / "demo" / "SKILL.md").write_text("broken")
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
        os.symlink(self.toolkit / "demo", self.project / ".claude/skills/demo")
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
        source = self.toolkit / "demo"

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
        other = self.make_skills_dir(
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
                    fsutil.tree_snapshot(winner / "demo"),
                )

    def test_private_umask_keeps_the_copy_identical_to_the_source(self):
        previous = os.umask(0o077)
        self.addCleanup(os.umask, previous)
        result = self.install()[0]
        self.assertEqual(result.status, "installed", result.detail)
        source = self.toolkit / "demo"
        installed = self.project / ".claude/skills/demo"
        self.assertEqual(installer.status_of(source, installed), "identical")
        self.assertTrue(os.access(installed / "scripts/run.sh", os.X_OK))

    def test_status_of(self):
        source = self.toolkit / "demo"
        dest = self.project / ".claude/skills/demo"
        self.assertEqual(installer.status_of(source, dest), "missing")
        self.install()
        self.assertEqual(installer.status_of(source, dest), "identical")
        (dest / "SKILL.md").write_text("changed")
        self.assertEqual(installer.status_of(source, dest), "differs")

    def test_tree_snapshot_propagates_unreadable_directory(self):
        source = self.toolkit / "demo"
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
        source = self.toolkit / "demo"
        dest = self.project / ".claude/skills/demo"
        self.install()
        os.chmod(dest, 0o000)
        self.addCleanup(os.chmod, dest, 0o755)
        self.assertEqual(installer.status_of(source, dest), "unsafe")


class LockedLifecycleTest(TempDirTest):
    """Install, update and uninstall of built-in skills, driven through the lock."""

    def setUp(self):
        super().setUp()
        self.toolkit = self.make_skills_dir({"demo": skill_text("demo")})
        self.project = self.make_project()
        self.dest = self.project / ".claude/skills/demo"

    def install(self, target="claude"):
        return installer.install(self.toolkit, "demo", target, project_dir=self.project)

    def update(self, *names, target="all", **kw):
        return installer.update(self.toolkit, list(names), target, project_dir=self.project, **kw)

    def uninstall(self, target="claude"):
        return installer.uninstall("demo", target, project_dir=self.project)

    def lock(self):
        return lockfile.read(self.project)

    def change_canonical(self, text="changed\n"):
        (self.toolkit / "demo/SKILL.md").write_text(skill_text("demo", "New text."))
        (self.toolkit / "demo/extra.md").write_text(text)
        (self.toolkit / "demo/scripts").mkdir(exist_ok=True)
        marker = self.tmp / "EXECUTED"
        script = self.toolkit / "demo/scripts/run.sh"
        script.write_text(f"#!/bin/sh\ntouch {marker}\n")
        os.chmod(script, 0o755)
        return marker

    def test_install_records_builtin_entry(self):
        self.install("all")
        entry = self.lock()["demo"]
        self.assertEqual(entry["source"], "builtin")
        self.assertEqual((entry["ref"], entry["path"], entry["commit"]), (None, None, None))
        self.assertEqual(entry["targets"], ["claude", "codex"])
        expected = lockfile.digest(fsutil.tree_snapshot(self.dest))
        self.assertEqual(entry["content_sha256"], expected)

    def test_conflicting_install_is_not_recorded(self):
        self.dest.mkdir(parents=True)
        (self.dest / "SKILL.md").write_text("mine\n")
        self.assertEqual(self.install()[0].status, "conflict")
        self.assertEqual(self.lock(), {})

    def test_install_of_changed_content_conflicts_with_lock(self):
        self.install("claude")
        self.change_canonical()
        result = self.install("codex")[0]
        self.assertEqual((result.status, result.exit_code), ("conflict", EXIT_CONFLICT))
        self.assertFalse((self.project / ".agents").exists())

    def test_update_replaces_pristine_copy_and_updates_lock(self):
        self.install("all")
        marker = self.change_canonical()
        results = self.update("demo")
        self.assertEqual([r.status for r in results], ["updated", "updated"])
        for sub in (".claude/skills/demo", ".agents/skills/demo"):
            self.assertEqual(
                fsutil.tree_snapshot(self.project / sub),
                fsutil.tree_snapshot(self.toolkit / "demo"),
            )
        expected = lockfile.digest(fsutil.tree_snapshot(self.dest))
        self.assertEqual(self.lock()["demo"]["content_sha256"], expected)
        self.assertEqual(os.listdir(self.project / ".engkit/staging"), [])
        self.assertEqual(os.listdir(self.dest.parent), ["demo"])
        self.assertFalse(marker.exists(), "updated scripts must never be executed")

    def test_update_all_and_up_to_date(self):
        self.install()
        self.assertEqual([r.status for r in self.update()], ["up to date"])
        self.change_canonical()
        self.assertEqual([r.status for r in self.update()], ["updated"])
        self.assertEqual([r.status for r in self.update()], ["up to date"])

    def test_update_modified_copy_conflicts_and_is_untouched(self):
        self.install()
        self.change_canonical()
        (self.dest / "SKILL.md").write_text("my edits\n")
        before, lock_before = snapshot(self.project), self.lock()
        result = self.update("demo")[0]
        self.assertEqual((result.status, result.exit_code), ("conflict", EXIT_CONFLICT))
        self.assertEqual(snapshot(self.project), before)
        self.assertEqual(self.lock(), lock_before)

    def test_update_unmanaged_is_refused(self):
        self.dest.mkdir(parents=True)
        (self.dest / "SKILL.md").write_text("mine\n")
        result = self.update("demo")[0]
        self.assertEqual((result.status, result.exit_code), ("not managed", 1))
        self.assertEqual((self.dest / "SKILL.md").read_text(), "mine\n")
        self.assertFalse((self.project / ".engkit").exists())

    def test_update_swap_failure_rolls_back(self):
        self.install()
        self.change_canonical()
        original, lock_before = fsutil.tree_snapshot(self.dest), self.lock()
        for stage in ("update_staged", "update_published"):

            def boom(hook_stage, target, stage=stage):
                if hook_stage == stage:
                    raise OSError("simulated failure")

            with self.subTest(stage=stage), mock.patch.object(installer, "fault_hook", boom):
                result = self.update("demo")[0]
            self.assertEqual((result.status, result.exit_code), ("error", EXIT_IO))
            self.assertEqual(fsutil.tree_snapshot(self.dest), original)
            self.assertEqual(self.lock(), lock_before)
            self.assertEqual(os.listdir(self.project / ".engkit/staging"), [])

    def test_failed_rollback_keeps_original_and_reports_it(self):
        self.install()
        self.change_canonical()

        def sabotage(stage, target):
            if stage == "update_published":
                shutil.rmtree(target)
                target.mkdir()
                (target / "intruder").write_text("x")
                raise OSError("simulated failure")

        with mock.patch.object(installer, "fault_hook", sabotage):
            result = self.update("demo")[0]
        self.assertEqual(result.status, "error")
        self.assertIn("original kept at", result.detail)
        self.assertEqual((self.dest / "intruder").read_text(), "x")
        kept = self.project / ".engkit/staging"
        self.assertTrue((next(kept.iterdir()) / "old/SKILL.md").is_file())

    def test_partial_update_failure_is_retryable(self):
        self.install("all")
        self.change_canonical()
        calls = []

        def fail_second(stage, target):
            if stage == "update_staged":
                calls.append(target)
                if len(calls) == 2:
                    raise OSError("simulated failure")

        with mock.patch.object(installer, "fault_hook", fail_second):
            statuses = [r.status for r in self.update("demo")]
        self.assertEqual(statuses, ["updated", "error"])
        retry = [r.status for r in self.update("demo")]
        self.assertEqual(retry, ["up to date", "updated"])
        expected = lockfile.digest(fsutil.tree_snapshot(self.dest))
        self.assertEqual(self.lock()["demo"]["content_sha256"], expected)

    def partial_update(self):
        self.install("all")
        self.change_canonical()
        calls = []

        def fail_second(stage, target):
            if stage == "update_staged":
                calls.append(target)
                if len(calls) == 2:
                    raise OSError("simulated failure")

        with mock.patch.object(installer, "fault_hook", fail_second):
            return [r.status for r in self.update("demo")]

    def test_uninstall_of_the_updated_target_after_a_partial_update_succeeds(self):
        self.assertEqual(self.partial_update(), ["updated", "error"])
        entry = self.lock()["demo"]
        self.assertEqual(set(entry["target_digests"]), {"claude"})
        self.assertEqual(self.uninstall("claude")[0].status, "uninstalled")
        self.assertFalse(self.dest.exists())
        entry = self.lock()["demo"]
        self.assertEqual(entry["targets"], ["codex"])
        self.assertNotIn("target_digests", entry)
        self.assertEqual([r.status for r in self.update("demo")], ["updated"])
        expected = lockfile.digest(fsutil.tree_snapshot(self.project / ".agents/skills/demo"))
        self.assertEqual(self.lock()["demo"]["content_sha256"], expected)

    def test_later_update_finishes_the_remaining_target_and_clears_the_map(self):
        self.partial_update()
        self.assertEqual([r.status for r in self.update("demo")], ["up to date", "updated"])
        self.assertNotIn("target_digests", self.lock()["demo"])
        self.assertEqual(self.uninstall("all")[0].status, "uninstalled")

    def test_global_scope_uses_home_lock(self):
        installer.install(self.toolkit, "demo", "codex", scope="user")
        self.change_canonical()
        result = installer.update(self.toolkit, [], "all", scope="user")[0]
        self.assertEqual(result.status, "updated")
        self.assertIn("demo", lockfile.read(self.home))
        self.assertTrue((self.home / ".agents/skills/demo/extra.md").is_file())
        self.assertEqual(
            installer.uninstall("demo", "codex", scope="user")[0].status, "uninstalled"
        )
        self.assertFalse((self.home / ".agents/skills/demo").exists())

    def test_uninstall_pristine_removes_and_drops_lock_entry(self):
        self.install("all")
        self.assertEqual(self.uninstall("claude")[0].status, "uninstalled")
        self.assertFalse(self.dest.exists())
        self.assertEqual(self.lock()["demo"]["targets"], ["codex"])
        self.assertEqual(self.uninstall("codex")[0].status, "uninstalled")
        self.assertEqual(self.lock(), {})
        self.assertEqual(os.listdir(self.project / ".engkit/staging"), [])

    def test_uninstall_of_a_manually_deleted_copy_drops_the_lock_target(self):
        self.install("all")
        shutil.rmtree(self.dest)
        other = self.project / ".agents/skills/demo"
        before = snapshot(other)
        result = self.uninstall("claude")[0]
        self.assertEqual((result.status, result.exit_code), ("uninstalled", 0))
        self.assertIn("already gone", result.detail)
        self.assertEqual(self.lock()["demo"]["targets"], ["codex"])
        self.assertEqual(snapshot(other), before)

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory permissions")
    def test_uninstall_with_an_unreadable_skills_dir_is_an_error_and_keeps_the_lock(self):
        self.install()
        skills_dir = self.dest.parent
        os.chmod(skills_dir, 0o000)
        self.addCleanup(os.chmod, skills_dir, 0o755)
        result = self.uninstall("claude")[0]
        self.assertEqual((result.status, result.exit_code), ("error", EXIT_IO))
        self.assertNotIn("already gone", result.detail)
        self.assertEqual(self.lock()["demo"]["targets"], ["claude"])

    def test_update_names_the_real_reason_when_another_target_is_missing(self):
        self.install("all")
        self.change_canonical()
        shutil.rmtree(self.dest)
        details = {r.platform: r.detail for r in self.update("demo")}
        self.assertIn("another target is missing", details["codex"])
        self.assertIn("uninstall the gone target, then update", details["codex"])
        self.assertNotIn("modified", details["codex"])

    def test_update_of_a_manually_deleted_copy_asks_for_a_reinstall(self):
        self.install("all")
        self.change_canonical()
        shutil.rmtree(self.dest)
        results = self.update("demo")
        self.assertEqual(results[0].status, "error")
        self.assertIn("reinstall", results[0].detail)
        self.assertFalse(self.dest.exists())
        self.assertNotIn("extra.md", os.listdir(self.project / ".agents/skills/demo"))

    def test_chmod_x_on_an_installed_file_is_a_modification(self):
        for action in ("update", "uninstall"):
            with self.subTest(action=action):
                self.install()
                self.change_canonical()
                os.chmod(self.dest / "SKILL.md", 0o755)
                result = {"update": lambda: self.update("demo"), "uninstall": self.uninstall}[
                    action
                ]()[0]
                self.assertEqual((result.status, result.exit_code), ("conflict", EXIT_CONFLICT))
                self.assertTrue(self.dest.exists())
                os.chmod(self.dest / "SKILL.md", 0o644)
                self.assertEqual(self.uninstall()[0].status, "uninstalled")  # mode restored

    def test_uninstall_modified_conflicts_and_is_untouched(self):
        self.install()
        (self.dest / "SKILL.md").write_text("my edits\n")
        before, lock_before = snapshot(self.project), self.lock()
        result = self.uninstall()[0]
        self.assertEqual((result.status, result.exit_code), ("conflict", EXIT_CONFLICT))
        self.assertEqual(snapshot(self.project), before)
        self.assertEqual(self.lock(), lock_before)

    def test_uninstall_without_lock_entry_is_not_managed(self):
        self.install("claude")
        self.assertEqual(self.uninstall("codex")[0].status, "not managed")
        self.dest.parent.mkdir(parents=True, exist_ok=True)
        other = self.project / ".agents/skills/demo"
        other.mkdir(parents=True)
        (other / "SKILL.md").write_text("hand made\n")
        self.assertEqual(self.uninstall("codex")[0].status, "not managed")
        self.assertTrue(other.exists())
        self.assertEqual(
            installer.uninstall("nope", "all", project_dir=self.project)[0].exit_code, 1
        )

    def test_uninstall_refuses_symlinked_destination(self):
        self.install()
        shutil.move(self.dest, self.tmp / "real")
        os.symlink(self.tmp / "real", self.dest)
        result = self.uninstall()[0]
        self.assertEqual(result.status, "conflict")
        self.assertTrue((self.tmp / "real/SKILL.md").exists())


def _loser_statuses(native: bool, expected: str) -> set[str]:
    # The reservation protocol exposes an empty directory while the winner publishes,
    # and a loser that inspects it then must report the retryable "busy" (ADR 0002).
    if native:
        return {"installed", expected}
    return {"installed", expected, "busy"}
