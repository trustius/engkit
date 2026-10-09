"""Fetch skills from git sources into a temporary checkout; fetched files are never run."""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from engkit import fsutil
from engkit.errors import EXIT_FAILURE, EXIT_USAGE, EngkitError

# Printable ASCII only; the first character after the scheme or "@host:" may not be "-".
URL_RE = re.compile(
    r"(?:(?:https|ssh|file)://[!-,.-~][!-~]*"
    r"|[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9.-]*:[!-,.-9;-~][!-~]*)\Z"
)
REF_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\Z")
CREDENTIALS_RE = re.compile(r"(://)[^/@\s]+@")
HARDENING = (
    "-c",
    "protocol.ext.allow=never",
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "advice.detachedHead=false",
)


@dataclass
class Fetched:
    root: Path
    commit: str


def redact(text: str) -> str:
    return CREDENTIALS_RE.sub(r"\1***@", text)


def check_source(url: str, ref: str | None, path: str | None) -> None:
    """Reject unsafe input before git runs."""
    if not URL_RE.match(url) or url.startswith(("ext::", "fd::")):
        message = (
            f"unsupported source URL {redact(url)!r} (use https://, ssh://, file:// or scp-style)"
        )
        raise EngkitError(message, EXIT_USAGE)
    if ref is not None and (not REF_RE.match(ref) or ".." in ref):
        raise EngkitError(f"invalid --ref {ref!r}", EXIT_USAGE)
    if path is not None:
        try:
            fsutil.safe_relpath(path, "--path")
        except fsutil.UnsafePathError as exc:
            raise EngkitError(str(exc), EXIT_USAGE) from None


def _git(arguments: list[str], cwd: Path) -> str:
    git = shutil.which("git")
    if git is None:
        raise EngkitError("git is required for --source but was not found on PATH", EXIT_FAILURE)
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"}
    timeout = float(os.environ.get("ENGKIT_GIT_TIMEOUT", "120"))
    try:
        done = subprocess.run(
            [git, *HARDENING, *arguments],
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise EngkitError(
            f"git {arguments[0]} timed out after {timeout:g}s", EXIT_FAILURE
        ) from None
    if done.returncode != 0:
        detail = redact(done.stderr.strip())
        raise EngkitError(f"git {arguments[0]} failed: {detail}", EXIT_FAILURE)
    return done.stdout.strip()


@contextlib.contextmanager
def fetch(url: str, ref: str | None = None, path: str | None = None):
    """Shallow checkout of ``url`` at ``ref`` (default HEAD) in a temp dir removed on exit."""
    check_source(url, ref, path)
    directory = Path(tempfile.mkdtemp(prefix="engkit-src-"))
    try:
        _git(["init", "-q"], directory)
        fetch_args = ["fetch", "-q", "--depth", "1", "--no-recurse-submodules", "--no-tags"]
        _git([*fetch_args, "--", url, ref or "HEAD"], directory)
        _git(["checkout", "-q", "FETCH_HEAD"], directory)
        yield Fetched(directory, _git(["rev-parse", "HEAD"], directory))
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def skills_dir(root: Path, path: str | None) -> Path:
    """``--path`` if given, else ``skills/`` if present, else the repository root."""
    if path is not None:
        found = root / path
    else:
        found = root / "skills" if (root / "skills").is_dir() else root
    if not fsutil.is_within(Path(os.path.realpath(found)), root.resolve()):
        raise EngkitError(
            f"skills path {found.name!r} resolves outside the repository", EXIT_FAILURE
        )
    return found


def preview_text(header: list[str], base: Path, names: list[str], validation: list[str]) -> str:
    lines = list(header)
    risky = []
    for name in names:
        lines.append(f"skill {name}:")
        for rel, size, is_risky in _files(base, name):
            lines.append(f"  {rel} ({size} bytes)")
            if is_risky:
                risky.append(rel)
    lines.append("risky files (executable bit or under scripts/; read before trusting):")
    lines.extend(f"  {rel}" for rel in risky or ["(none)"])
    lines.extend(validation)
    lines.append("nothing installed; re-run with --yes to install")
    return "\n".join(lines)


def _files(base: Path, name: str):
    for dirpath, dirnames, filenames in os.walk(base / name):
        dirnames.sort()
        for filename in sorted(filenames):
            full = Path(dirpath) / filename
            info = os.lstat(full)
            parts = full.relative_to(base / name).parts
            risky = bool(info.st_mode & 0o111) or "scripts" in parts[:-1]
            yield full.relative_to(base).as_posix(), info.st_size, risky
