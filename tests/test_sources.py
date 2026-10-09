import os
import shutil
import unittest
from unittest import mock

from engkit import lockfile, sources
from engkit.errors import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, EngkitError
from tests.helpers import TempDirTest, commit_all, git, make_repo, run_cli, skill_text, snapshot

HAS_GIT = shutil.which("git") is not None


class ValidationTest(TempDirTest):
    def test_bad_urls_are_rejected_before_git_runs(self):
        bad = [
            "ext::sh -c touch /tmp/pwned",
            "fd::3",
            "-oProxyCommand=x",
            "--upload-pack=x",
            "/tmp/some/repo",
            "relative/repo",
            "http://example.test/r.git",
            "https://-x.example/r",
            "https://host/a b",
            "ssh://host/r\n--x",
            "-u@host:path",
            "user@host:-x",
            "",
        ]
        with mock.patch("subprocess.run") as run:
            for url in bad:
                with self.subTest(url=url), self.assertRaises(EngkitError) as caught:
                    sources.check_source(url, None, None)
                self.assertEqual(caught.exception.exit_code, EXIT_USAGE)
            run.assert_not_called()

    def test_good_urls_ref_and_path_are_accepted(self):
        for url in (
            "https://example.test/r.git",
            "ssh://git@h/r",
            "file:///tmp/r",
            "git@h.test:o/r",
        ):
            sources.check_source(url, "v1.2/rc-1", "skills/team")

    def test_bad_refs_and_paths(self):
        url = "https://example.test/r.git"
        for ref in ("-x", "a..b", "a b", "", "x;y", "a\nb"):
            with self.subTest(ref=ref), self.assertRaises(EngkitError):
                sources.check_source(url, ref, None)
        for path in ("../x", "/abs", "a/../b", "", "a//b"):
            with self.subTest(path=path), self.assertRaises(EngkitError):
                sources.check_source(url, None, path)

    def test_credentials_are_redacted(self):
        self.assertNotIn("secret", sources.redact("fatal: https://bob:secret@host/r.git"))

    def test_missing_git_is_a_clear_error(self):
        with mock.patch("shutil.which", return_value=None), self.assertRaises(EngkitError) as c:
            sources._git(["status"], self.tmp)
        self.assertIn("git", str(c.exception))

    def test_cli_rejects_bad_source_with_usage_exit(self):
        code, _, err = run_cli(["list", "--source", "ext::sh -c id"])
        self.assertEqual(code, EXIT_USAGE)
        self.assertIn("unsupported source URL", err)


@unittest.skipUnless(HAS_GIT, "git is required")
class FetchTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.repo = make_repo(self.tmp / "remote", {"skills/demo/SKILL.md": skill_text("demo")})
        self.url = f"file://{self.repo}"
        self.first = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "tag", "v1")
        git(self.repo, "checkout", "-q", "-b", "feature")
        (self.repo / "skills/demo/extra.md").write_text("more\n")
        self.second = commit_all(self.repo)
        git(self.repo, "checkout", "-q", "main")

    def fetch_commit(self, ref):
        with sources.fetch(self.url, ref) as fetched:
            return fetched.commit

    def test_fetch_by_default_branch_tag_and_commit(self):
        self.assertEqual(self.fetch_commit(None), self.first)
        self.assertEqual(self.fetch_commit("v1"), self.first)
        self.assertEqual(self.fetch_commit("feature"), self.second)
        self.assertEqual(self.fetch_commit(self.second), self.second)

    def test_checkout_is_removed_afterwards(self):
        with sources.fetch(self.url) as fetched:
            self.assertTrue((fetched.root / "skills/demo/SKILL.md").is_file())
        self.assertFalse(fetched.root.exists())

    def test_nonexistent_ref_is_a_clear_error(self):
        with self.assertRaises(EngkitError) as caught:
            self.fetch_commit("no-such-branch")
        self.assertIn("git fetch failed", str(caught.exception))

    def test_skills_dir_defaults_and_symlink_escape(self):
        with sources.fetch(self.url) as fetched:
            self.assertEqual(sources.skills_dir(fetched.root, None), fetched.root / "skills")
            self.assertEqual(sources.skills_dir(fetched.root, "skills"), fetched.root / "skills")
        root = self.tmp / "flat"
        root.mkdir()
        (root / "skills").symlink_to(self.tmp)
        with self.assertRaises(EngkitError):
            sources.skills_dir(root, None)


@unittest.skipUnless(HAS_GIT, "git is required")
class RemoteInstallTest(TempDirTest):
    def setUp(self):
        super().setUp()
        files = {
            "skills/demo/SKILL.md": skill_text("demo", extra="\n[s](scripts/run.sh)\n"),
            "skills/demo/scripts/run.sh": f"#!/bin/sh\ntouch {self.tmp}/EXECUTED\n",
            "skills/demo/references/a.md": "ref\n",
        }
        self.repo = make_repo(self.tmp / "remote", files)
        os.chmod(self.repo / "skills/demo/scripts/run.sh", 0o755)
        self.commit = commit_all(self.repo)
        self.url = f"file://{self.repo}"
        self.project = self.make_project()

    def install(self, *extra, url=None, skills=("demo",)):
        argv = ["install", "--source", url or self.url, "--target", "claude"]
        for name in skills:
            argv += ["--skill", name]
        argv += ["--project-dir", str(self.project), *extra]
        return run_cli(argv)

    def lock(self):
        return lockfile.read(self.project)

    def test_preview_writes_nothing_and_lists_risky_files(self):
        before = (snapshot(self.project), snapshot(self.home))
        code, out, _ = self.install()
        self.assertEqual(code, EXIT_OK)
        self.assertIn("preview", out)
        self.assertIn(self.commit, out)
        self.assertIn("demo/scripts/run.sh", out.split("risky files")[1])
        self.assertIn("nothing installed", out)
        self.assertEqual((snapshot(self.project), snapshot(self.home)), before)
        self.assertFalse((self.project / ".engkit").exists())

    def test_install_yes_records_lock_and_never_executes(self):
        code, out, _ = self.install("--yes")
        self.assertEqual(code, EXIT_OK)
        self.assertIn(self.commit, out)
        installed = self.project / ".claude/skills/demo"
        self.assertTrue(os.access(installed / "scripts/run.sh", os.X_OK))
        self.assertFalse((self.tmp / "EXECUTED").exists())
        entry = self.lock()["demo"]
        self.assertEqual(entry["source"], self.url)
        self.assertEqual((entry["commit"], entry["targets"]), (self.commit, ["claude"]))
        self.assertEqual(entry["content_sha256"], self._digest(installed))

    def _digest(self, path):
        from engkit import fsutil

        return lockfile.digest(fsutil.tree_snapshot(path))

    def test_repeat_install_is_already_installed_and_lock_unchanged(self):
        self.install("--yes")
        before = (self.project / ".engkit/skills.lock.json").read_bytes()
        code, out, _ = self.install("--yes")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("already installed", out)
        self.assertEqual((self.project / ".engkit/skills.lock.json").read_bytes(), before)

    def test_same_name_from_different_source_conflicts(self):
        self.install("--yes")
        other = make_repo(
            self.tmp / "other", {"skills/demo/SKILL.md": skill_text("demo", "Other one.")}
        )
        before = snapshot(self.project)
        code, _, err = self.install("--yes", url=f"file://{other}")
        self.assertEqual(code, 3)
        self.assertIn("conflict", err)
        self.assertEqual(snapshot(self.project), before)

    def test_invalid_remote_skill_writes_nothing(self):
        make_repo(self.tmp / "bad", {"skills/demo/SKILL.md": "no frontmatter\n"})
        for flags in ((), ("--yes",)):
            with self.subTest(flags=flags):
                code, _, err = self.install(*flags, url=f"file://{self.tmp / 'bad'}")
                self.assertEqual(code, EXIT_FAILURE)
                self.assertIn("failed validation", err)
                self.assertEqual(os.listdir(self.project), [])

    def test_unknown_skill_name_is_an_error(self):
        code, _, err = self.install("--yes", skills=("missing",))
        self.assertEqual(code, EXIT_FAILURE)
        self.assertEqual(os.listdir(self.project), [])

    def test_remote_symlink_is_refused(self):
        repo = make_repo(self.tmp / "link", {"skills/demo/SKILL.md": skill_text("demo")})
        (repo / "skills/demo/leak").symlink_to("/etc/hosts")
        commit_all(repo)
        for flags in ((), ("--yes",)):
            with self.subTest(flags=flags):
                code, _, err = self.install(*flags, url=f"file://{repo}")
                self.assertEqual(code, EXIT_FAILURE)
                self.assertIn("symlink", err)
                self.assertEqual(os.listdir(self.project), [])

    def test_ref_by_sha_and_path(self):
        nested = make_repo(self.tmp / "nested", {"pkg/team/demo/SKILL.md": skill_text("demo")})
        sha = git(nested, "rev-parse", "HEAD")
        code, _, _ = self.install(
            "--yes", "--ref", sha, "--path", "pkg/team", url=f"file://{nested}"
        )
        self.assertEqual(code, EXIT_OK)
        entry = self.lock()["demo"]
        self.assertEqual((entry["ref"], entry["path"], entry["commit"]), (sha, "pkg/team", sha))

    def test_remote_skill_without_shared_guardrails_installs(self):
        files = {"skills/plain/SKILL.md": skill_text("plain", shared_guardrails=False)}
        repo = make_repo(self.tmp / "plain-remote", files)
        url = f"file://{repo}"
        code, out, _ = self.install(url=url, skills=("plain",))
        self.assertEqual((code, "preview" in out), (EXIT_OK, True))
        code, out, _ = self.install("--yes", url=url, skills=("plain",))
        self.assertEqual(code, EXIT_OK, out)
        self.assertTrue((self.project / ".claude/skills/plain/SKILL.md").is_file())
        (repo / "skills/plain/SKILL.md").write_text(
            skill_text("plain", extra="\nMore.\n", shared_guardrails=False)
        )
        commit_all(repo)
        argv = ["update", "plain", "--project-dir", str(self.project), "--yes"]
        code, out, _ = run_cli(argv)
        self.assertEqual((code, "updated" in out), (EXIT_OK, True), out)

    def test_remote_update_needs_yes_and_shows_commits(self):
        self.install("--yes")
        (self.repo / "skills/demo/references/a.md").write_text("changed\n")
        new_commit = commit_all(self.repo)
        argv = ["update", "demo", "--project-dir", str(self.project)]
        before = snapshot(self.project)
        code, out, _ = run_cli(argv)
        self.assertEqual(code, EXIT_OK)
        self.assertIn(f"{self.commit} -> {new_commit}", out)
        self.assertEqual(snapshot(self.project), before)
        code, out, _ = run_cli([*argv, "--yes"])
        self.assertEqual((code, "updated" in out), (EXIT_OK, True))
        installed = self.project / ".claude/skills/demo/references/a.md"
        self.assertEqual(installed.read_text(), "changed\n")
        self.assertEqual(self.lock()["demo"]["commit"], new_commit)
        self.assertEqual(
            self.lock()["demo"]["content_sha256"],
            self._digest(self.project / ".claude/skills/demo"),
        )
        self.assertFalse((self.tmp / "EXECUTED").exists())

    def test_remote_update_unchanged_is_up_to_date_without_yes(self):
        self.install("--yes")
        code, out, _ = run_cli(["update", "--project-dir", str(self.project)])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("up to date", out)

    def test_unchanged_content_with_a_moved_commit_leaves_the_lock_alone(self):
        self.install("--yes")
        (self.repo / "unrelated.txt").write_text("x\n")
        new_commit = commit_all(self.repo)
        lock_path = lockfile.lock_file(self.project)
        before = lock_path.read_bytes()
        argv = ["update", "--project-dir", str(self.project)]
        code, out, _ = run_cli(argv)
        self.assertEqual((code, "up to date" in out), (EXIT_OK, True))
        self.assertEqual(lock_path.read_bytes(), before)
        run_cli([*argv, "--yes"])
        self.assertEqual(self.lock()["demo"]["commit"], new_commit)


if __name__ == "__main__":
    unittest.main()


class HostileSourceTest(TempDirTest):
    def test_invalid_date_in_remote_skill_is_reported_without_traceback(self):
        files = {
            "skills/demo/SKILL.md": skill_text("demo").replace(
                "name: demo\n", "name: demo\nupdated: 2026-13-45\n", 1
            )
        }
        repo = make_repo(self.tmp / "remote", files)
        code, _, err = run_cli(["list", "--source", f"file://{repo}"])
        self.assertEqual(code, EXIT_FAILURE)
        self.assertNotIn("Traceback", err)
        self.assertIn("frontmatter", err)

    def test_deeply_nested_frontmatter_in_remote_skill_is_reported(self):
        text = skill_text("demo").replace("name: demo\n", "name: demo\nx: " + "[" * 3000 + "\n", 1)
        repo = make_repo(self.tmp / "remote", {"skills/demo/SKILL.md": text})
        code, out, err = run_cli(["list", "--source", f"file://{repo}"])
        self.assertEqual(code, EXIT_FAILURE)
        self.assertNotIn("Traceback", err)
        self.assertIn("too deeply nested", out + err)

    def test_nul_byte_in_link_is_a_validation_error_in_the_preview(self):
        repo = make_repo(
            self.tmp / "remote",
            {"skills/demo/SKILL.md": skill_text("demo", extra="\n[x](bad\x00name.md)\n")},
        )
        project = self.make_project()
        argv = ["install", "--source", f"file://{repo}", "--skill", "demo", "--target", "claude"]
        code, out, err = run_cli([*argv, "--project-dir", str(project)])
        self.assertEqual(code, EXIT_FAILURE)
        self.assertNotIn("Traceback", err)
        self.assertIn("invalid reference", out + err)

    def test_missing_path_is_a_clean_error_without_temp_directory(self):
        repo = make_repo(self.tmp / "remote", {"skills/demo/SKILL.md": skill_text("demo")})
        code, out, err = run_cli(["list", "--source", f"file://{repo}", "--path", "nope"])
        self.assertEqual(code, EXIT_FAILURE)
        self.assertTrue(err.startswith("engkit: error:"), err)
        self.assertIn("nope", err)
        self.assertNotIn("engkit-src-", out + err)
        self.assertNotIn(str(self.tmp), out + err)
