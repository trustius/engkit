"""``.engkit/skills.lock.json``: what engkit installed, from where, and its content hash."""

from __future__ import annotations

import contextlib
import json
import os
import re
import stat
from pathlib import Path

from engkit import fsutil, platforms
from engkit.errors import EXIT_FAILURE, EXIT_IO, EngkitError
from engkit.validator import validate_name

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

LOCK_NAME = "skills.lock.json"
ENTRY_KEYS = {"source", "ref", "path", "commit", "content_sha256", "targets"}
MAX_LOCK_BYTES = 1024 * 1024
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def lock_file(root: Path) -> Path:
    return root / ".engkit" / LOCK_NAME


def digest(snapshot: dict[str, str]) -> str:
    lines = "".join(f"{path}\0{value}\n" for path, value in sorted(snapshot.items()))
    return fsutil.sha256_bytes(lines.encode())


def expected_digest(entry: dict, platform_id: str) -> str:
    """The digest an installed copy for ``platform_id`` must have to count as pristine."""
    return entry.get("target_digests", {}).get(platform_id, entry["content_sha256"])


def require_locking() -> None:
    if fcntl is None:
        raise EngkitError("lockfile updates are unsupported on this platform", EXIT_FAILURE)


def _entry_problem(name: str, entry: object) -> str:
    """Describe what is wrong with one entry, or return an empty string."""
    message = validate_name(name)
    if message:
        return f"invalid skill name: {message}"
    if not isinstance(entry, dict) or not set(entry) >= ENTRY_KEYS:
        return "malformed entry"
    if not isinstance(entry["source"], str):
        return "source must be a string"
    for key in ("ref", "path", "commit"):
        if entry[key] is not None and not isinstance(entry[key], str):
            return f"{key} must be a string or null"
    if not isinstance(entry["content_sha256"], str) or not SHA256_RE.match(entry["content_sha256"]):
        return "content_sha256 must be 64 lower-case hex digits"
    targets = entry["targets"]
    if not isinstance(targets, list) or not set(targets) <= set(platforms.PLATFORMS):
        return "targets must be a list of known platforms"
    return _target_digests_problem(entry.get("target_digests"), targets)


def _target_digests_problem(digests: object, targets: list) -> str:
    if digests is None:
        return ""
    if not isinstance(digests, dict) or not set(digests) <= set(targets):
        return "target_digests must map locked targets to digests"
    if not all(isinstance(item, str) and SHA256_RE.match(item) for item in digests.values()):
        return "target_digests values must be 64 lower-case hex digits"
    return ""


def _parse(text: str, path: Path) -> dict:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise EngkitError(f"{path} is not valid JSON ({exc}); fix or delete it") from None
    skills = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(skills, dict) or data.get("lock_version") != 1:
        raise EngkitError(f"{path} has an unsupported structure (lock_version 1 expected)")
    for name, entry in skills.items():
        problem = _entry_problem(name, entry)
        if problem:
            raise EngkitError(f"{path}: entry {name!r}: {problem}; fix or delete it")
    return skills


def read(root: Path) -> dict:
    """Return the skills mapping; empty when no lock exists. Never creates anything."""
    path = lock_file(root)
    if fsutil.check_no_symlinks(root, (".engkit",)):
        raise EngkitError(f"refusing symlinked {path.parent}", EXIT_FAILURE)
    text = _read_text(path)
    return _parse(text, path) if text else {}


def _read_text(path: Path) -> str:
    """Read a small regular file without following a symlink or blocking on a FIFO."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return ""
    except OSError as exc:
        raise EngkitError(f"cannot read {path}: {exc.strerror}", EXIT_FAILURE) from None
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_LOCK_BYTES:
            raise EngkitError(f"{path} must be a regular file of at most 1 MiB", EXIT_FAILURE)
        return handle.read(MAX_LOCK_BYTES + 1).decode("utf-8", errors="replace")


def _dump(skills: dict) -> str:
    return json.dumps({"lock_version": 1, "skills": skills}, indent=2, sort_keys=True) + "\n"


@contextlib.contextmanager
def transaction(root: Path):
    """Yield the skills mapping under an exclusive lock; it is saved only if it changed."""
    require_locking()
    try:
        directory = fsutil.ensure_real_dirs(root, (".engkit",))
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        handle = os.fdopen(os.open(directory / f"{LOCK_NAME}.lock", flags, 0o644), "r")
    except fsutil.UnsafePathError as exc:
        raise EngkitError(f"cannot use .engkit: {exc}", EXIT_FAILURE) from None
    except OSError as exc:
        raise EngkitError(f"cannot open the lock under .engkit: {exc}", EXIT_IO) from None
    with handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        skills = read(root)
        before = _dump(skills)
        yield skills
        text = _dump(skills)
        if text != before:
            fsutil.replace_file(directory / LOCK_NAME, text.encode())
