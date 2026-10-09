"""Locate bundled toolkit resources independent of the caller's cwd.

An installed distribution carries ``engkit/_resources/`` (copied by the build
hook in setup.py). A source checkout (editable install or ``PYTHONPATH=src``)
falls back to the repository root, located relative to this file. The current
working directory is never consulted.
"""

from __future__ import annotations

from pathlib import Path

RESOURCE_DIRS = ("skills", "packs", "schemas", "templates", "stacks")


class ResourceError(RuntimeError):
    pass


def _is_resource_root(path: Path) -> bool:
    return all((path / name).is_dir() for name in RESOURCE_DIRS)


def resource_root() -> Path:
    package_dir = Path(__file__).resolve().parent
    bundled = package_dir / "_resources"
    if _is_resource_root(bundled):
        return bundled
    checkout = package_dir.parent.parent
    if _is_resource_root(checkout) and (checkout / "pyproject.toml").is_file():
        return checkout
    raise ResourceError(
        f"engkit resources not found: expected {bundled} (installed) or a source checkout at {checkout}"
    )


def resource_origin(root: Path) -> str:
    return "bundled" if root.name == "_resources" else "checkout"
