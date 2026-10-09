"""Fetch skills from git sources into a temporary checkout; fetched files are never run."""

from __future__ import annotations

import contextlib
import itertools
import math
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from engkit import fsutil
from engkit.errors import EXIT_FAILURE, EXIT_USAGE, EngkitError

# Printable ASCII only; the first character after the scheme or "@host:" may not be "-".
URL_RE = re.compile(
    r"(?:(?:https|ssh|file)://[!-,.-~][!-~]*"
    r"|[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9.-]*:[!-,.-9;-~][!-~]*)\Z"
)
REF_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\Z")
URL_IN_TEXT_RE = re.compile(r"(?:https?|ssh|file)://[^\s'\"<>]+")
GIT_CONFIG = (
    "protocol.ext.allow=never",
    "core.hooksPath=/dev/null",
    "advice.detachedHead=false",
    "submodule.recurse=false",
    "core.fsmonitor=false",
)
# GIT_* variables that may reach git; GIT_ASKPASS and the repository-selecting ones may not.
GIT_KEEP = ("GIT_SSH", "GIT_SSH_COMMAND", "GIT_SSL_CAINFO", "GIT_SSL_CAPATH")
CREDENTIAL_ADVICE = (
    "source URL must not embed credentials, a query string or a fragment; "
    "use a git credential helper or ssh instead"
)


@dataclass
class Fetched:
    root: Path
    commit: str


def _strip_userinfo(match: re.Match) -> str:
    url = match.group()
    try:
        netloc = urlsplit(url).netloc
    except ValueError:
        return "<url>"
    return url.replace(netloc, netloc.rpartition("@")[2], 1)


def redact(text: str) -> str:
    """Drop ``user:password@`` from every URL in ``text``."""
    return URL_IN_TEXT_RE.sub(_strip_userinfo, text)


def _has_credentials(url: str) -> bool:
    if "?" in url or "#" in url:
        return True
    parts = urlsplit(url)
    userinfo = parts.netloc.rpartition("@")[0]
    return bool(userinfo) and (parts.scheme == "https" or ":" in userinfo)


def check_source(url: str, ref: str | None, path: str | None) -> None:
    """Reject unsafe input before git runs."""
    if not URL_RE.match(url):
        message = (
            f"unsupported source URL {redact(url)!r} (use https://, ssh://, file:// or scp-style)"
        )
        raise EngkitError(message, EXIT_USAGE)
    if _has_credentials(url):
        raise EngkitError(CREDENTIAL_ADVICE, EXIT_USAGE)
    if ref is not None and (not REF_RE.match(ref) or ".." in ref):
        raise EngkitError(f"invalid --ref {ref!r}", EXIT_USAGE)
    if path is not None:
        try:
            fsutil.safe_relpath(path, "--path")
        except fsutil.UnsafePathError as exc:
            raise EngkitError(str(exc), EXIT_USAGE) from None


def _git_environment() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update({key: os.environ[key] for key in GIT_KEEP if key in os.environ})
    environment.update(
        GIT_TERMINAL_PROMPT="0", GIT_LFS_SKIP_SMUDGE="1", GIT_ASKPASS="", SSH_ASKPASS=""
    )
    if "GIT_SSH" not in environment:
        environment.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    return environment


def _timeout() -> float:
    raw = os.environ.get("ENGKIT_GIT_TIMEOUT", "120")
    try:
        seconds = float(raw)
    except ValueError:
        seconds = 0.0
    if not 0 < seconds < math.inf:
        message = f"ENGKIT_GIT_TIMEOUT must be a positive number of seconds, got {raw!r}"
        raise EngkitError(message, EXIT_USAGE)
    return seconds


def _git(arguments: list[str], cwd: Path) -> str:
    git = shutil.which("git")
    if git is None:
        raise EngkitError("git is required for --source but was not found on PATH", EXIT_FAILURE)
    timeout = _timeout()
    options = itertools.chain.from_iterable(("-c", option) for option in GIT_CONFIG)
    # Explicit locations so an ambient GIT_DIR or a parent repository can never be used.
    argv = [git, *options, f"--git-dir={cwd / '.git'}", f"--work-tree={cwd}", *arguments]
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=_git_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException as exc:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        if not isinstance(exc, subprocess.TimeoutExpired):
            raise
        message = f"git {arguments[0]} timed out after {timeout:g}s"
        raise EngkitError(message, EXIT_FAILURE) from None
    if process.returncode != 0:
        raise EngkitError(f"git {arguments[0]} failed: {redact(stderr.strip())}", EXIT_FAILURE)
    return stdout.strip()


@contextlib.contextmanager
def fetch(url: str, ref: str | None = None, path: str | None = None):
    """Shallow checkout of ``url`` at ``ref`` (default HEAD) in a temp dir removed on exit."""
    check_source(url, ref, path)
    directory = Path(tempfile.mkdtemp(prefix="engkit-src-"))
    try:
        _git(["init", "-q"], directory)
        flags = ["--depth", "1", "--no-recurse-submodules", "--no-tags"]
        _git(["fetch", "-q", *flags, "--", url, ref or "HEAD"], directory)
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
    if not Path(os.path.realpath(found)).is_relative_to(root.resolve()):
        raise EngkitError(
            f"skills path {found.name!r} resolves outside the repository", EXIT_FAILURE
        )
    return found


def preview_text(header: list[str], base: Path, names: list[str], validation: list[str]) -> str:
    lines = list(header)
    risky = []
    for name in names:
        files = list(_files(base, name))
        lines.append(f"skill {name}:")
        lines.extend(f"  {relative} ({size} bytes)" for relative, size, _ in files)
        risky.extend(relative for relative, _, is_risky in files if is_risky)
    lines.append("risky files (executable bit or under scripts/; read before trusting):")
    lines.extend(f"  {relative}" for relative in risky or ["(none)"])
    lines.extend(validation)
    lines.append("nothing installed; re-run with --yes to install")
    return "\n".join(fsutil.printable(line) for line in lines)


def _files(base: Path, name: str):
    """Yield (path relative to ``base``, size, risky) for every file of a skill."""
    for key, path in fsutil.entries(base / name):
        info = os.lstat(path)
        if stat.S_ISDIR(info.st_mode):
            continue
        risky = bool(info.st_mode & 0o111) or "scripts" in key.split("/")[:-1]
        yield path.relative_to(base).as_posix(), info.st_size, risky
