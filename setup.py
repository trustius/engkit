"""Build hook: bundle canonical resources into the distribution.

The canonical sources stay at the repository root (skills/, packs/, schemas/,
templates/, stacks/). At build time they are copied into
``engkit/_resources/`` inside the built package so an installed engkit never
depends on the caller's working directory or a source checkout.
"""

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

RESOURCE_DIRS = ("skills", "packs", "schemas", "templates", "stacks")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


class BuildWithResources(build_py):
    def run(self):
        super().run()
        root = Path(__file__).resolve().parent
        target = Path(self.build_lib) / "engkit" / "_resources"
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        for name in RESOURCE_DIRS:
            src = root / name
            if not src.is_dir():
                raise SystemExit(f"missing resource directory: {src}")
            # symlinks=True keeps links as links so the packaged validator
            # still rejects escaping symlinks instead of silently inlining them.
            shutil.copytree(src, target / name, symlinks=True, ignore=IGNORE)


setup(cmdclass={"build_py": BuildWithResources})
