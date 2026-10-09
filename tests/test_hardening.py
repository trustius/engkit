"""Regression tests for the security and correctness review findings."""

import os
import shutil
import stat
import unittest
from pathlib import Path
from unittest import mock

from engkit import catalog, fsutil, installer, lockfile, sources, validator
from engkit.errors import EXIT_CONFLICT, EXIT_FAILURE, EXIT_OK, EXIT_USAGE, EngkitError
from tests.helpers import TempDirTest, commit_all, make_repo, run_cli, skill_text, snapshot

HAS_GIT = shutil.which("git") is not None
MIB = 1024 * 1024


class FakePopen:
    calls: list = []

    def __init__(self, argv, **kwargs):
        FakePopen.calls.append((argv, kwargs))
        self.returncode = 0
        self.pid = 1

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def communicate(self, input=None, timeout=None):
        return "", ""

    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0


class GitEnvironmentTest(TempDirTest):
    def run_git(self, extra_env=None):
        FakePopen.calls = []
        with (
            mock.patch.dict(os.environ, extra_env or {}),
            mock.patch("subprocess.Popen", FakePopen),
        ):
            sources._git(["status"], self.tmp)
        return FakePopen.calls[0]

    def test_git_variables_are_scrubbed_and_prompts_disabled(self):
        argv, kwargs = self.run_git(
            {"GIT_DIR": "/x", "GIT_WORK_TREE": "/x", "GIT_EXEC_PATH": "/x", "GIT_ASKPASS": "/x"}
        )
        env = kwargs["env"]
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_EXEC_PATH"):
            self.assertNotIn(name, env)
        self.assertEqual(env["GIT_ASKPASS"], "")
        self.assertEqual(env["SSH_ASKPASS"], "")
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(env["GIT_LFS_SKIP_SMUDGE"], "1")
        self.assertIn("BatchMode=yes", env["GIT_SSH_COMMAND"])
        self.assertTrue(kwargs["start_new_session"])
        self.assertIn(f"--git-dir={self.tmp / '.git'}", argv)
        self.assertIn(f"--work-tree={self.tmp}", argv)
        for option in ("submodule.recurse=false", "core.fsmonitor=false"):
            self.assertIn(option, argv)

    def test_allowlisted_variables_survive(self):
        allowed = {
            "GIT_SSH_COMMAND": "ssh -i mykey",
            "GIT_SSL_CAINFO": "/ca",
            "HTTPS_PROXY": "http://proxy",
            "no_proxy": "localhost",
            "SSL_CERT_FILE": "/cert",
        }
        env = self.run_git(allowed)[1]["env"]
        for name, value in allowed.items():
            self.assertEqual(env[name], value)
        self.assertIn("PATH", env)
        self.assertIn("HOME", env)

    @unittest.skipUnless(HAS_GIT, "git is required")
    def test_ambient_git_dir_cannot_redirect_the_fetch(self):
        victim = make_repo(self.tmp / "victim", {"a.txt": "a\n"})
        remote = make_repo(self.tmp / "remote", {"skills/demo/SKILL.md": skill_text("demo")})
        before = snapshot(victim)
        ambient = {
            "GIT_DIR": str(victim / ".git"),
            "GIT_WORK_TREE": str(victim),
            "GIT_INDEX_FILE": str(victim / ".git/index"),
        }
        with mock.patch.dict(os.environ, ambient), sources.fetch(f"file://{remote}") as fetched:
            self.assertTrue((fetched.root / "skills/demo/SKILL.md").is_file())
        self.assertEqual(snapshot(victim), before)

    def test_invalid_timeout_is_a_clear_error(self):
        for value in ("abc", "0", "-5", "nan"):
            with (
                self.subTest(value=value),
                mock.patch.dict(os.environ, {"ENGKIT_GIT_TIMEOUT": value}),
            ):
                with self.assertRaises(EngkitError) as caught:
                    sources._git(["status"], self.tmp)
                self.assertIn("ENGKIT_GIT_TIMEOUT", str(caught.exception))

    def test_timeout_kills_the_whole_process_group(self):
        fake = self.tmp / "bin"
        fake.mkdir()
        script = fake / "git"
        script.write_text("#!/bin/sh\nsleep 5\n")
        script.chmod(0o755)
        env = {"PATH": f"{fake}:{os.environ['PATH']}", "ENGKIT_GIT_TIMEOUT": "0.5"}
        killpg = mock.patch("engkit.sources.os.killpg", wraps=os.killpg)
        with (
            mock.patch.dict(os.environ, env),
            killpg as spy,
            self.assertRaises(EngkitError) as caught,
        ):
            sources._git(["status"], self.tmp)
        spy.assert_called_once()
        self.assertIn("timed out", str(caught.exception))


class CredentialTest(TempDirTest):
    def test_credentials_in_urls_are_rejected(self):
        bad = (
            "https://user:tok@host.test/r.git",
            "https://token@host.test/r.git",
            "ssh://git:pw@host.test/r",
            "https://host.test/r.git?token=abc",
            "https://host.test/r.git#frag",
            "git@host.test:o/r?x=1",
        )
        for url in bad:
            with self.subTest(url=url), self.assertRaises(EngkitError) as caught:
                sources.check_source(url, None, None)
            self.assertEqual(caught.exception.exit_code, EXIT_USAGE)
            self.assertNotIn("tok", str(caught.exception).replace("token@", ""))
        with self.assertRaises(EngkitError) as caught:
            sources.check_source("https://u:tok@host.test/r", None, None)
        self.assertIn("credential helper", str(caught.exception))

    def test_username_only_ssh_forms_stay_allowed(self):
        for url in ("git@host.test:o/r", "ssh://git@host.test/o/r"):
            sources.check_source(url, None, None)

    def test_redaction_drops_userinfo_even_with_at_in_password(self):
        text = sources.redact("fatal: https://bob:p@ss@host.test/r.git not found")
        self.assertNotIn("bob", text)
        self.assertNotIn("p@ss", text)
        self.assertIn("https://host.test/r.git", text)


class PrintableTest(TempDirTest):
    def test_printable_escapes_control_characters(self):
        self.assertEqual(fsutil.printable("a\nb\x1b[2K\t"), "a\\x0ab\\x1b[2K\\x09")
        self.assertEqual(fsutil.printable("plain text"), "plain text")

    def test_validator_rejects_control_characters_in_names(self):
        toolkit = self.make_toolkit({"demo": skill_text("demo")})
        for bad in ("a\nb", "x\x1b[2Kz"):
            path = toolkit / "skills/demo" / bad
            path.write_text("x")
            result = validator.validate(toolkit, "demo")
            self.assertTrue(
                any("control character" in issue.message for issue in result.issues), bad
            )
            for issue in result.issues:
                self.assertNotIn("\x1b", issue.format())
            path.unlink()

    def test_preview_text_escapes_file_names(self):
        base = self.tmp / "base"
        (base / "demo").mkdir(parents=True)
        (base / "demo" / "a\nb\x1b[2K").write_text("x")
        text = sources.preview_text([], base, ["demo"], [])
        self.assertNotIn("\x1b", text)
        self.assertIn("demo/a\\x0ab\\x1b[2K", text)


@unittest.skipUnless(HAS_GIT, "git is required")
class FetchedOutputTest(TempDirTest):
    def test_list_source_escapes_descriptions(self):
        files = {"skills/demo/SKILL.md": skill_text("demo", '"evil\\e[2Kx"')}
        repo = make_repo(self.tmp / "remote", files)
        code, out, err = run_cli(["list", "--source", f"file://{repo}"])
        self.assertEqual(code, EXIT_OK)
        self.assertNotIn("\x1b", out + err)
        self.assertIn("evil\\x1b[2Kx", out)

    def test_install_preview_escapes_bad_file_names(self):
        repo = make_repo(self.tmp / "remote", {"skills/demo/SKILL.md": skill_text("demo")})
        (repo / "skills/demo" / "x\x1b[2Kz").write_text("x")
        commit_all(repo)
        project = self.make_project()
        argv = ["install", "--source", f"file://{repo}", "--skill", "demo", "--target", "claude"]
        code, out, err = run_cli([*argv, "--project-dir", str(project)])
        self.assertEqual(code, EXIT_FAILURE)
        self.assertNotIn("\x1b", out + err)
        self.assertIn("control character", err)


class SizeLimitTest(TempDirTest):
    def validate_with(self, files: dict[str, int]):
        toolkit = self.make_toolkit({"demo": skill_text("demo")})
        for name, size in files.items():
            path = toolkit / "skills/demo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x" * size)
        return [issue.message for issue in validator.validate(toolkit, "demo").issues]

    def test_file_count_limit(self):
        ok = self.validate_with({f"r/{i}.md": 1 for i in range(499)})
        self.assertFalse([m for m in ok if "files" in m])
        self.tearDown()
        self.setUp()
        too_many = self.validate_with({f"r/{i}.md": 1 for i in range(500)})
        self.assertTrue([m for m in too_many if "more than 500 files" in m])

    def test_single_file_limit(self):
        self.assertFalse([m for m in self.validate_with({"a.bin": MIB}) if "1 MiB" in m])
        self.tearDown()
        self.setUp()
        messages = self.validate_with({"a.bin": MIB + 1})
        self.assertTrue([m for m in messages if "larger than 1 MiB" in m])

    def test_total_size_limit(self):
        messages = self.validate_with({f"b{i}.bin": MIB for i in range(11)})
        self.assertTrue([m for m in messages if "larger than 10 MiB in total" in m])

    def test_oversized_skill_md_is_not_read(self):
        toolkit = self.make_toolkit({"demo": skill_text("demo") + "x" * (MIB + 1)})
        result = catalog.discover(toolkit)
        self.assertEqual(result.skills, [])
        self.assertIn("larger than 1 MiB", result.issues[0].message)

    def test_copy_streams_in_chunks_and_keeps_modes(self):
        source = self.tmp / "src"
        source.mkdir()
        (source / "run.sh").write_bytes(b"x" * 100)
        (source / "run.sh").chmod(0o755)
        no_read = mock.patch.object(Path, "read_bytes", side_effect=AssertionError("whole file"))
        chunked = mock.patch("shutil.copyfileobj", wraps=shutil.copyfileobj)
        with no_read, chunked as copy:
            fsutil.copy_tree_regular(source, self.tmp / "dst")
        copy.assert_called_once()
        mode = stat.S_IMODE(os.lstat(self.tmp / "dst/run.sh").st_mode)
        self.assertEqual(mode, 0o755)


class LifecycleFixesTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.toolkit = self.make_toolkit({"demo": skill_text("demo")})
        self.project = self.make_project()
        self.dest = self.project / ".claude/skills/demo"
        self.staging = self.project / ".engkit/staging"

    def install(self, target="claude", **options):
        options.setdefault("project_dir", self.project)
        return installer.install(self.toolkit, "demo", target, **options)

    def update(self, target="all", **options):
        return installer.update(self.toolkit, ["demo"], target, project_dir=self.project, **options)

    def uninstall(self, target="claude"):
        return installer.uninstall("demo", target, project_dir=self.project)

    def change_upstream(self):
        (self.toolkit / "skills/demo/extra.md").write_text("new\n")

    def hook(self, actions: dict):
        def run(stage, path):
            action = actions.get(stage)
            if action:
                action(path)

        return mock.patch.object(installer, "fault_hook", run)

    def tamper(self, path):
        (path / "SKILL.md").write_text("sneaky\n")

    def occupy(self, path):
        path.mkdir()
        (path / "intruder").write_text("x")

    def test_update_rehashes_the_moved_copy_and_puts_it_back(self):
        self.install()
        self.change_upstream()
        lock_before = lockfile.read(self.project)
        with self.hook({"update_checked": self.tamper}):
            result = self.update()[0]
        self.assertEqual((result.status, result.exit_code), ("conflict", EXIT_CONFLICT))
        self.assertEqual((self.dest / "SKILL.md").read_text(), "sneaky\n")
        self.assertEqual(lockfile.read(self.project), lock_before)
        self.assertEqual(os.listdir(self.staging), [])

    def test_update_keeps_the_moved_copy_when_destination_is_occupied(self):
        self.install()
        self.change_upstream()
        actions = {"update_checked": self.tamper, "update_moved": self.occupy}
        with self.hook(actions):
            result = self.update()[0]
        self.assertEqual(result.status, "conflict")
        self.assertIn("kept at", result.detail)
        kept = next(self.staging.iterdir()) / "old/SKILL.md"
        self.assertEqual(kept.read_text(), "sneaky\n")
        self.assertEqual((self.dest / "intruder").read_text(), "x")

    def test_uninstall_rehashes_the_moved_copy_and_puts_it_back(self):
        self.install()
        lock_before = lockfile.read(self.project)
        with self.hook({"uninstall_checked": self.tamper}):
            result = self.uninstall()[0]
        self.assertEqual((result.status, result.exit_code), ("conflict", EXIT_CONFLICT))
        self.assertEqual((self.dest / "SKILL.md").read_text(), "sneaky\n")
        self.assertEqual(lockfile.read(self.project), lock_before)

    def test_keyboard_interrupt_after_move_aside_restores_the_original(self):
        self.install()
        self.change_upstream()
        original = fsutil.tree_snapshot(self.dest)

        def interrupt(path):
            raise KeyboardInterrupt

        with self.hook({"update_moved": interrupt}), self.assertRaises(KeyboardInterrupt):
            self.update()
        self.assertEqual(fsutil.tree_snapshot(self.dest), original)
        self.assertEqual(os.listdir(self.staging), [])

    def test_keyboard_interrupt_with_failed_restore_keeps_the_only_copy(self):
        self.install()
        self.change_upstream()

        def occupy_and_interrupt(path):
            self.occupy(path)
            raise KeyboardInterrupt

        with (
            self.hook({"update_moved": occupy_and_interrupt}),
            self.assertRaises(KeyboardInterrupt),
        ):
            self.update()
        kept = next(self.staging.iterdir()) / "old/SKILL.md"
        self.assertTrue(kept.is_file())

    def test_partial_target_update_is_refused(self):
        self.install("all")
        self.change_upstream()
        before, lock_before = snapshot(self.project), lockfile.read(self.project)
        result = self.update("claude")[0]
        self.assertEqual((result.status, result.exit_code), ("error", EXIT_FAILURE))
        self.assertIn("codex", result.detail)
        self.assertEqual(snapshot(self.project), before)
        self.assertEqual(lockfile.read(self.project), lock_before)

    def test_failing_cleanup_after_uninstall_still_succeeds(self):
        self.install()

        def strict_rmtree(path, ignore_errors=False, **kwargs):
            if not ignore_errors:
                raise OSError("simulated cleanup failure")

        with mock.patch("engkit.installer.shutil.rmtree", strict_rmtree):
            result = self.uninstall()[0]
        self.assertEqual(result.status, "uninstalled")
        self.assertFalse(self.dest.exists())
        self.assertEqual(lockfile.read(self.project), {})

    def test_race_on_lock_clash_is_detected_inside_the_transaction(self):
        def other_source_wins(path):
            with lockfile.transaction(self.project) as skills:
                skills["demo"] = {
                    "source": "https://elsewhere.test/r",
                    "ref": None,
                    "path": None,
                    "commit": None,
                    "content_sha256": "b" * 64,
                    "targets": ["codex"],
                }

        with self.hook({"staged": other_source_wins}):
            result = self.install()[0]
        self.assertEqual((result.status, result.exit_code), ("conflict", EXIT_CONFLICT))
        entry = lockfile.read(self.project)["demo"]
        self.assertEqual(entry["source"], "https://elsewhere.test/r")
        self.assertEqual(entry["targets"], ["codex"])

    def test_missing_fcntl_fails_before_anything_is_published(self):
        with mock.patch.object(lockfile, "fcntl", None), self.assertRaises(EngkitError):
            self.install()
        self.assertFalse((self.project / ".claude").exists())

    def test_identical_unmanaged_destination_is_adopted_into_the_lock(self):
        fsutil.copy_tree_regular(self.toolkit / "skills/demo", self.dest_made())
        result = self.install()[0]
        self.assertEqual(result.status, "already installed")
        self.assertEqual(lockfile.read(self.project)["demo"]["targets"], ["claude"])

    def dest_made(self):
        self.dest.parent.mkdir(parents=True)
        return self.dest

    def test_validation_failure_reports_only_managed_targets(self):
        self.install("claude")
        (self.toolkit / "skills/demo/SKILL.md").write_text("broken")
        results = self.update("all")
        self.assertEqual([(r.platform, r.status) for r in results], [("claude", "error")])

    def test_update_with_nothing_to_change_does_not_write_the_lock(self):
        self.install("all")
        path = lockfile.lock_file(self.project)
        before = (path.read_bytes(), os.stat(path).st_ino, os.stat(path).st_mtime_ns)
        self.assertEqual([r.status for r in self.update()], ["up to date", "up to date"])
        after = (path.read_bytes(), os.stat(path).st_ino, os.stat(path).st_mtime_ns)
        self.assertEqual(after, before)


class CliArgumentTest(TempDirTest):
    def test_remote_only_flags_without_source_are_usage_errors(self):
        for flag in (["--yes"], ["--skill", "y"], ["--ref", "main"], ["--path", "d"]):
            with self.subTest(flag=flag):
                code, _, _ = run_cli(["install", "x", "--target", "claude", *flag])
                self.assertEqual(code, EXIT_USAGE)

    def test_invalid_names_are_usage_errors(self):
        project = ["--project-dir", str(self.make_project())]
        for argv in (
            ["uninstall", "../x", "--target", "claude"],
            ["update", "Bad_Name"],
            ["install", "../x", "--target", "claude"],
        ):
            with self.subTest(argv=argv):
                self.assertEqual(run_cli([*argv, *project])[0], EXIT_USAGE)


@unittest.skipUnless(HAS_GIT, "git is required")
class UpdateContinuesTest(TempDirTest):
    def test_one_failed_fetch_does_not_stop_the_other_updates(self):
        project = self.make_project()
        gone = make_repo(self.tmp / "gone", {"skills/aaa/SKILL.md": skill_text("aaa")})
        kept = make_repo(self.tmp / "kept", {"skills/demo/SKILL.md": skill_text("demo")})
        for repo, name in ((gone, "aaa"), (kept, "demo")):
            argv = ["install", "--source", f"file://{repo}", "--skill", name, "--yes"]
            code, _, _ = run_cli([*argv, "--target", "claude", "--project-dir", str(project)])
            self.assertEqual(code, EXIT_OK)
        shutil.rmtree(gone)
        code, out, err = run_cli(["update", "--yes", "--project-dir", str(project)])
        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("aaa", err)
        self.assertIn("git fetch failed", err)
        self.assertIn("demo: up to date", out)


if __name__ == "__main__":
    unittest.main()
