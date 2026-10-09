"""Shared test helpers. Every test uses temporary project and home directories."""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent

SKILL_BODY = """
# {name}

## When to use
Use for synthetic tests. Not for anything else.

## When to ask
Ask when the input is ambiguous.

## Objective
Test.

## Inputs
None.

## Workflow
1. Do the thing.

## Output contract
Report verified fact, plausible hypothesis and untested assumption.

## Guardrails
No edits.
"""


def skill_text(
    name: str, description: str = "A synthetic skill for tests.", extra: str = ""
) -> str:
    return (
        f"---\nname: {name}\ndescription: {description}\n---\n"
        + SKILL_BODY.format(name=name)
        + extra
    )


class TempDirTest(unittest.TestCase):
    """Provides self.tmp (Path), plus isolated HOME so nothing touches the real home."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="engkit-test-")
        self.tmp = Path(self._tmp.name).resolve()
        self.home = self.tmp / "home"
        self.home.mkdir()
        patcher = mock.patch.dict(
            os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home)}
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for dirpath, dirnames, _ in os.walk(self.tmp):
            for d in dirnames:
                p = Path(dirpath) / d
                if not p.is_symlink():
                    os.chmod(p, 0o755)
        self._tmp.cleanup()

    def make_toolkit(
        self, skills: dict[str, str] | None = None, copy_real: bool = False, name: str = "toolkit"
    ) -> Path:
        """A toolkit root containing skills/."""
        root = self.tmp / name
        root.mkdir()
        if copy_real:
            shutil.copytree(REPO / "skills", root / "skills")
        else:
            (root / "skills").mkdir()
        for name, text in (skills or {}).items():
            d = root / "skills" / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(text)
        return root

    def make_project(self, name: str = "project", files: dict[str, str] | None = None) -> Path:
        root = self.tmp / name
        root.mkdir(parents=True)
        for rel, text in (files or {}).items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        return root


def snapshot(root: Path) -> dict[str, object]:
    """All entries (files with bytes, dirs, symlinks) below root, for no-write assertions."""
    out: dict[str, object] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in dirnames + filenames:
            p = Path(dirpath) / name
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                out[rel] = ("link", os.readlink(p))
            elif p.is_dir():
                out[rel] = "dir"
            else:
                out[rel] = p.read_bytes()
    return out


def run_cli(argv: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    from engkit.cli import main

    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    try:
        if cwd:
            os.chdir(cwd)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(argv)
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
    finally:
        os.chdir(old)
    return code, out.getvalue(), err.getvalue()


@contextlib.contextmanager
def resources_at(root: Path):
    with mock.patch("engkit.resources.resource_root", return_value=root):
        yield
