"""Built-distribution tests: sdist -> wheel -> clean venv, run outside the source checkout.

Offline: `python -m build --no-isolation` and `pip wheel --no-index` use the running
interpreter's build tools, and the test venv sees the interpreter's PyYAML through a .pth
file. The source copy is deleted before the wheel is built. Set ENGKIT_SKIP_DIST=1 to skip.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from email.parser import Parser
from pathlib import Path

import yaml

from tests.helpers import REPO, SKILLS_DIR, TempDirTest

SKIP = os.environ.get("ENGKIT_SKIP_DIST") == "1"
PYTHON = sys.executable
SOURCE_IGNORE = shutil.ignore_patterns(
    ".venv", "build", "dist", "*.egg-info", "__pycache__", ".engkit", ".git", ".ruff_cache"
)
FORBIDDEN_PARTS = ("tests", "evals", ".venv", "__pycache__", "docs")


def run_command(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    hidden = ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")
    environment = {key: value for key, value in os.environ.items() if key not in hidden}
    process = subprocess.run(
        argv, cwd=cwd, env=environment, capture_output=True, text=True, timeout=300
    )
    if process.returncode != 0:
        raise AssertionError(
            f"{argv} failed ({process.returncode}):\n{process.stdout}\n{process.stderr}"
        )
    return process


def build_wheel_from_sdist(workspace: Path) -> Path:
    source = workspace / "src-copy"
    shutil.copytree(REPO, source, ignore=SOURCE_IGNORE)
    dist = workspace / "dist"
    sdist_command = [PYTHON, "-m", "build", "--sdist", "--no-isolation", "--outdir", str(dist)]
    run_command([*sdist_command, str(source)], cwd=workspace)
    sdist = next(dist.glob("engkit-*.tar.gz"))
    shutil.rmtree(source)  # the source checkout is unavailable from here on
    wheel_command = [PYTHON, "-m", "pip", "wheel", str(sdist), "--no-deps", "--no-index"]
    run_command([*wheel_command, "--no-build-isolation", "-w", str(dist)], cwd=workspace)
    return next(dist.glob("engkit-*.whl"))


def install_into_venv(wheel: Path, venv: Path) -> Path:
    run_command([PYTHON, "-m", "venv", "--system-site-packages", str(venv)], cwd=venv.parent)
    site_packages = next(venv.glob("lib/python*/site-packages"))
    yaml_parent = Path(yaml.__file__).resolve().parent.parent
    (site_packages / "host_yaml.pth").write_text(f"{yaml_parent}\n")
    venv_python = str(venv / "bin" / "python")
    run_command([venv_python, "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)], venv)
    return venv / "bin" / "engkit"


@unittest.skipIf(SKIP, "ENGKIT_SKIP_DIST=1")
class DistributionTest(TempDirTest):
    @classmethod
    def setUpClass(cls):
        cls._workspace = tempfile.TemporaryDirectory(prefix="engkit-dist-")
        workspace = Path(cls._workspace.name).resolve()
        cls.wheel = build_wheel_from_sdist(workspace)
        cls.venv = workspace / "venv"
        cls.engkit = str(install_into_venv(cls.wheel, cls.venv))

    @classmethod
    def tearDownClass(cls):
        cls._workspace.cleanup()

    def test_wheel_contains_every_skill_and_nothing_else(self):
        with zipfile.ZipFile(self.wheel) as archive:
            names = archive.namelist()
        expected = {
            f"engkit/skills/{path.parent.name}/SKILL.md" for path in SKILLS_DIR.glob("*/SKILL.md")
        }
        self.assertEqual(len(expected), 6)
        self.assertTrue(expected <= set(names), sorted(expected - set(names)))
        for name in names:
            parts = name.split("/")
            self.assertFalse(any(part in FORBIDDEN_PARTS for part in parts), name)

    def test_version_matches_wheel_metadata(self):
        with zipfile.ZipFile(self.wheel) as archive:
            metadata_name = next(
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            )
            metadata = Parser().parsestr(archive.read(metadata_name).decode())
        output = run_command([self.engkit, "--version"], cwd=self.tmp).stdout
        self.assertEqual(output.strip(), f"engkit {metadata['Version']}")
        self.assertEqual(metadata["Requires-Python"], ">=3.11")

    def test_installed_cli_works_from_an_unrelated_directory(self):
        elsewhere = self.make_project("unrelated-cwd")
        listing = json.loads(run_command([self.engkit, "list", "--json"], cwd=elsewhere).stdout)
        self.assertEqual(len(listing["skills"]), 6)
        run_command([self.engkit, "validate"], cwd=elsewhere)
        project = self.make_project("consumer", {"README.md": "consumer\n"})
        install = [self.engkit, "install", "bug-investigate", "--target", "all"]
        run_command([*install, "--project-dir", str(project)], cwd=elsewhere)
        reference = ".claude/skills/bug-investigate/references/root-cause-analysis.md"
        self.assertTrue((project / reference).is_file())
        self.assertTrue((project / ".agents/skills/bug-investigate/SKILL.md").is_file())
        doctor_command = [self.engkit, "doctor", "--project-dir", str(project), "--project-only"]
        doctor = json.loads(run_command([*doctor_command, "--json"], cwd=elsewhere).stdout)
        environment_lines = " ".join(item["message"] for item in doctor["sections"][0]["items"])
        self.assertIn(f"skills: {self.venv / 'lib'}", environment_lines)
        self.assertNotIn(str(REPO), environment_lines)
