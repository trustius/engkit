"""``.engkit/skills.lock.json``: what engkit installed, from where, and its content hash."""

from __future__ import annotations

import contextlib
import json
import os
import uuid
from pathlib import Path

from engkit import fsutil
from engkit.errors import EXIT_FAILURE, EXIT_IO, EngkitError

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

LOCK_NAME = "skills.lock.json"
ENTRY_KEYS = {"source", "ref", "path", "commit", "content_sha256", "targets"}


def lock_file(root: Path) -> Path:
    return root / ".engkit" / LOCK_NAME


def digest(snapshot: dict[str, str]) -> str:
    lines = "".join(f"{path}\0{value}\n" for path, value in sorted(snapshot.items()))
    return fsutil.sha256_bytes(lines.encode())


def _parse(text: str, path: Path) -> dict:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise EngkitError(
            f"{path} is not valid JSON ({exc}); fix or delete it", EXIT_FAILURE
        ) from None
    skills = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(skills, dict) or data.get("lock_version") != 1:
        raise EngkitError(f"{path} has an unsupported structure (lock_version 1 expected)")
    for name, entry in skills.items():
        if not isinstance(entry, dict) or not set(entry) >= ENTRY_KEYS:
            raise EngkitError(f"{path}: entry '{name}' is malformed", EXIT_FAILURE)
        if not isinstance(entry["targets"], list):
            raise EngkitError(f"{path}: entry '{name}' has invalid targets", EXIT_FAILURE)
    return skills


def read(root: Path) -> dict:
    """Return the skills mapping; empty when no lock exists. Never creates anything."""
    path = lock_file(root)
    if fsutil.check_no_symlinks(root, (".engkit",)):
        raise EngkitError(f"refusing symlinked {path.parent}", EXIT_FAILURE)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    return _parse(text, path)


def _write(path: Path, skills: dict) -> None:
    data = json.dumps({"lock_version": 1, "skills": skills}, indent=2, sort_keys=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        fsutil.write_file(temporary, (data + "\n").encode())
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise
    fsutil.fsync_dir(path.parent)


@contextlib.contextmanager
def transaction(root: Path):
    """Yield the skills mapping under an exclusive lock; it is saved if the block succeeds."""
    if fcntl is None:
        raise EngkitError("lockfile updates are unsupported on this platform", EXIT_FAILURE)
    try:
        directory = fsutil.ensure_real_dirs(root, (".engkit",))
    except fsutil.UnsafePathError as exc:
        raise EngkitError(f"cannot use .engkit: {exc}", EXIT_FAILURE) from None
    except OSError as exc:
        raise EngkitError(f"cannot create .engkit: {exc}", EXIT_IO) from None
    with open(directory / f"{LOCK_NAME}.lock", "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        skills = read(root)
        yield skills
        _write(directory / LOCK_NAME, skills)
