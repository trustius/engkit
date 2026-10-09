"""Built-distribution test: wheel installed outside the checkout, run from an unrelated cwd.

Offline: the wheel is built with --no-index --no-build-isolation using the
interpreter's existing build and setuptools, and the test venv reuses the interpreter's
already-installed PyYAML (--system-site-packages). The source copy used for
the build is deleted before the installed CLI runs. Set ENGKIT_SKIP_DIST=1 to skip.
"""

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

from tests.helpers import REPO, TempDirTest

SKIP = os.environ.get("ENGKIT_SKIP_DIST") == "1"
PYTHON = sys.executable


@unittest.skipIf(SKIP, "ENGKIT_SKIP_DIST=1")
class DistributionTest(TempDirTest):
    def run_cmd(self, argv, cwd, check=True):
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")
        }
        proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
        if check and proc.returncode != 0:
            self.fail(f"{argv} failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
        return proc

    def expose_yaml(self, venv):
        """Make the running interpreter's PyYAML importable offline inside the test venv."""
        site_packages = next(venv.glob("lib/python*/site-packages"))
        yaml_parent = Path(yaml.__file__).resolve().parent.parent
        (site_packages / "host_yaml.pth").write_text(f"{yaml_parent}\n")

    def test_wheel_works_without_source_checkout(self):
        src = self.tmp / "src-copy"
        shutil.copytree(
            REPO,
            src,
            ignore=shutil.ignore_patterns(
                ".venv", "build", "dist", "*.egg-info", "__pycache__", ".engkit", ".git"
            ),
        )
        dist = self.tmp / "dist"
        # Build via the sdist so content missing from the sdist fails here.
        self.run_cmd(
            [PYTHON, "-m", "build", "--sdist", "--no-isolation", "--outdir", str(dist), str(src)],
            cwd=self.tmp,
        )
        sdist = next(dist.glob("engkit-*.tar.gz"))
        shutil.rmtree(src)  # the source checkout is unavailable from here on
        self.run_cmd(
            [
                PYTHON,
                "-m",
                "pip",
                "wheel",
                str(sdist),
                "--no-deps",
                "--no-index",
                "--no-build-isolation",
                "-w",
                str(dist),
            ],
            cwd=self.tmp,
        )
        wheel = next(dist.glob("engkit-*.whl"))

        venv = self.tmp / "venv"
        self.run_cmd([PYTHON, "-m", "venv", "--system-site-packages", str(venv)], cwd=self.tmp)
        self.expose_yaml(venv)
        self.run_cmd(
            [
                str(venv / "bin" / "python"),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                str(wheel),
            ],
            cwd=self.tmp,
        )
        engkit = str(venv / "bin" / "engkit")

        elsewhere = self.make_project("unrelated-cwd")
        out = self.run_cmd([engkit, "list", "--json"], cwd=elsewhere).stdout
        self.assertEqual(len(json.loads(out)["skills"]), 6)
        self.run_cmd([engkit, "validate"], cwd=elsewhere)

        project = self.make_project("consumer", {"README.md": "consumer\n"})
        self.run_cmd(
            [
                engkit,
                "install",
                "systematic-debugging",
                "--target",
                "all",
                "--project-dir",
                str(project),
            ],
            cwd=elsewhere,
        )
        self.assertTrue(
            (
                project / ".claude/skills/systematic-debugging/references/root-cause-analysis.md"
            ).is_file()
        )
        self.assertTrue((project / ".agents/skills/systematic-debugging/SKILL.md").is_file())

        doctor = json.loads(
            self.run_cmd(
                [engkit, "doctor", "--project-dir", str(project), "--project-only", "--json"],
                cwd=elsewhere,
            ).stdout
        )
        env_lines = " ".join(i["message"] for i in doctor["sections"][0]["items"])
        self.assertIn("skills: ", env_lines)
        self.assertIn(str(venv / "lib"), env_lines)
        self.assertNotIn(str(REPO), env_lines)
