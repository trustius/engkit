"""Static checks on the GitHub Actions workflows (no network, no execution)."""

import re
import unittest
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
SHA_PATTERN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def load(name: str) -> dict:
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    # YAML 1.1 parses the bare key ``on`` as boolean True.
    if True in data:
        data["on"] = data.pop(True)
    return data


def steps_of(job: dict) -> list:
    return job.get("steps", [])


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.ci = load("ci.yml")
        self.release = load("release.yml")

    def test_all_actions_pinned_to_full_sha(self):
        for name, workflow in (("ci", self.ci), ("release", self.release)):
            for job_name, job in workflow["jobs"].items():
                for step in steps_of(job):
                    if "uses" in step:
                        self.assertRegex(
                            step["uses"], SHA_PATTERN, f"{name}/{job_name}: {step['uses']}"
                        )

    def test_release_top_level_permissions_empty(self):
        self.assertEqual(self.release["permissions"], {})

    def test_only_publish_jobs_have_id_token_write(self):
        for job_name, job in self.release["jobs"].items():
            token = job.get("permissions", {}).get("id-token")
            if job_name.startswith("publish-"):
                self.assertEqual(token, "write", job_name)
                self.assertEqual(job["permissions"], {"id-token": "write"})
            else:
                self.assertIsNone(token, job_name)
        self.assertNotIn("id-token", self.release["jobs"]["build"].get("permissions", {}))
        for job in self.ci["jobs"].values():
            self.assertNotIn("id-token", job.get("permissions", {}))
        self.assertNotIn("id-token", self.ci["permissions"])

    def test_publish_jobs_have_no_checkout_and_use_artifact(self):
        for job_name in ("publish-testpypi", "publish-pypi"):
            uses = [step.get("uses", "") for step in steps_of(self.release["jobs"][job_name])]
            self.assertFalse(any(u.startswith("actions/checkout@") for u in uses), job_name)
            self.assertTrue(any(u.startswith("actions/download-artifact@") for u in uses))
            self.assertTrue(any(u.startswith("pypa/gh-action-pypi-publish@") for u in uses))

    def test_publish_chain_and_environments(self):
        jobs = self.release["jobs"]
        self.assertEqual(jobs["check"]["needs"], "build")
        self.assertEqual(jobs["publish-testpypi"]["needs"], ["build", "check"])
        self.assertEqual(jobs["publish-pypi"]["needs"], ["build", "publish-testpypi"])
        self.assertEqual(jobs["publish-testpypi"]["environment"]["name"], "testpypi")
        self.assertEqual(jobs["publish-pypi"]["environment"]["name"], "pypi")

    def test_release_build_is_hash_locked_and_on_main(self):
        build_runs = " ".join(
            step.get("run", "") for step in steps_of(self.release["jobs"]["build"])
        )
        self.assertIn('git merge-base --is-ancestor "$GITHUB_SHA" origin/main', build_runs)
        self.assertIn("--require-hashes", build_runs)
        self.assertIn("requirements/release-build.txt", build_runs)
        self.assertIn("python -m build --no-isolation", build_runs)
        self.assertNotIn("twine", build_runs, "twine must not run where the artifact is built")
        lock = (WORKFLOWS.parent.parent / "requirements" / "release-build.txt").read_text()
        pins = re.findall(r"^([A-Za-z0-9_.-]+)==\S+ \\\n\s+--hash=sha256:[0-9a-f]{64}$", lock, re.M)
        self.assertEqual(sorted(pins), ["build", "packaging", "pyproject_hooks", "setuptools"])

    def test_artifact_digest_verified_before_check_and_publish(self):
        jobs = self.release["jobs"]
        self.assertIn("digest", jobs["build"]["outputs"])
        for job_name in ("check", "publish-testpypi", "publish-pypi"):
            runs = " ".join(step.get("run", "") for step in steps_of(jobs[job_name]))
            self.assertIn("$EXPECTED_DIGEST", runs, job_name)

    def test_testpypi_does_not_skip_existing(self):
        for step in steps_of(self.release["jobs"]["publish-testpypi"]):
            self.assertNotIn("skip-existing", step.get("with", {}))

    def test_ci_matrix(self):
        matrix = self.ci["jobs"]["test"]["strategy"]["matrix"]
        self.assertFalse(self.ci["jobs"]["test"]["strategy"]["fail-fast"])
        self.assertFalse(any("windows" in item for item in matrix["os"]))
        self.assertEqual(set(matrix["python"]), {"3.11", "3.12", "3.13"})

    def test_no_dangerous_triggers_or_secrets(self):
        for name in ("ci.yml", "release.yml"):
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            self.assertNotIn("pull_request_target", text, name)
            self.assertNotIn("workflow_run", text, name)
            self.assertNotIn("secrets.", text, name)

    def test_no_expressions_in_release_run_blocks(self):
        for job_name, job in self.release["jobs"].items():
            for step in steps_of(job):
                if "run" in step:
                    self.assertNotIn("${{", step["run"], job_name)

    def test_release_triggers_only_on_version_tags(self):
        trigger = self.release["on"]
        self.assertEqual(list(trigger), ["push"])
        self.assertEqual(trigger["push"], {"tags": ["v*"]})

    def test_all_jobs_have_timeouts(self):
        for workflow in (self.ci, self.release):
            for job_name, job in workflow["jobs"].items():
                self.assertIn("timeout-minutes", job, job_name)

    def test_release_concurrency_does_not_cancel(self):
        self.assertFalse(self.release["concurrency"]["cancel-in-progress"])


if __name__ == "__main__":
    unittest.main()
