"""Copy-based, staged, no-replace installation of canonical skills.

Contract: docs/adr/0002-installation-safety.md. Existing destinations are never
deleted or modified; only this operation's staging directory is cleaned up.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from engkit import fsutil, platforms
from engkit.errors import EXIT_BUSY, EXIT_CONFLICT, EXIT_FAILURE, EXIT_IO, EXIT_OK
from engkit.validator import validate

INSTALLED = "installed"
ALREADY = "already installed"
CONFLICT = "conflict"
BUSY = "busy"
ERROR = "error"

STATUS_EXIT = {INSTALLED: EXIT_OK, ALREADY: EXIT_OK, CONFLICT: EXIT_CONFLICT, BUSY: EXIT_BUSY}

STAGE_MARKER = ".engkit-stage-"

# Test seam called with ("staged" | "before_publish", destination path).
fault_hook = None


@dataclass
class InstallResult:
    platform: str
    scope: str
    skill: str
    destination: Path
    status: str
    detail: str = ""
    exit_code: int = EXIT_OK

    def format(self) -> str:
        line = f"[{self.platform}] {self.skill}: {self.status} -> {self.destination}"
        return f"{line}\n    {self.detail}" if self.detail else line


def resolve_root(
    scope: str, project_dir: str | os.PathLike | None, home_dir: str | os.PathLike | None
) -> Path:
    if scope == "project":
        raw = Path(project_dir) if project_dir is not None else Path.cwd()
    else:
        raw = Path(home_dir) if home_dir is not None else Path.home()
    root = raw.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")
    return root


def _failures(
    targets: list[platforms.Platform], scope: str, name: str, detail: str, exit_code: int
) -> list[InstallResult]:
    return [
        InstallResult(item.id, scope, name, Path("-"), ERROR, detail, exit_code) for item in targets
    ]


def install(
    toolkit_root: Path,
    name: str,
    target: str,
    *,
    scope: str = "project",
    project_dir: str | os.PathLike | None = None,
    home_dir: str | os.PathLike | None = None,
    allow_native_noreplace: bool = True,
) -> list[InstallResult]:
    """Install one skill to each requested platform; returns one result per platform."""
    targets = platforms.expand_target(target)
    report = validate(toolkit_root, name)
    errors = [issue for issue in report.issues if issue.level == "error"]
    if errors or not report.skills:
        detail = "; ".join(issue.format() for issue in errors) or "unknown skill"
        return _failures(targets, scope, name, f"source failed validation: {detail}", EXIT_FAILURE)
    source = report.skills[0].path
    try:
        source_hash = fsutil.tree_snapshot(source, allow_symlinks=False)
    except (fsutil.UnsafePathError, OSError) as exc:
        return _failures(targets, scope, name, str(exc), EXIT_FAILURE)
    try:
        root = resolve_root(scope, project_dir, home_dir)
    except OSError as exc:
        return _failures(targets, scope, name, f"cannot resolve root: {exc}", EXIT_IO)

    results = []
    for platform in targets:
        destination = platforms.destination(platform, scope, root)
        results.append(_install_one(source, source_hash, name, destination, allow_native_noreplace))
    return results


def _install_one(
    source: Path,
    source_hash: dict,
    name: str,
    destination: platforms.Destination,
    native: bool,
) -> InstallResult:
    target = destination.skill_path(name)

    def result(status: str, detail: str = "", code: int | None = None) -> InstallResult:
        exit_code = STATUS_EXIT.get(status, EXIT_FAILURE) if code is None else code
        return InstallResult(
            destination.platform.id, destination.scope, name, target, status, detail, exit_code
        )

    # Parents are checked before inspecting the target so a symlinked skills
    # directory cannot make an existing copy look installed.
    problems = fsutil.check_no_symlinks(destination.root, destination.parts)
    if problems:
        return result(ERROR, f"unsafe destination: {problems[0]}", EXIT_FAILURE)
    # Cheap early answer; publication below re-checks atomically.
    early = _inspect_existing(target, source_hash)
    if early is not None:
        return result(*early)
    try:
        skills_dir = fsutil.ensure_real_dirs(destination.root, destination.parts)
    except fsutil.UnsafePathError as exc:
        return result(ERROR, f"unsafe destination: {exc}", EXIT_FAILURE)
    except OSError as exc:
        return result(ERROR, f"cannot create destination parents: {exc}", EXIT_IO)
    return _stage_and_publish(source, source_hash, skills_dir, target, native, result)


def _stage_and_publish(source, source_hash, skills_dir, target, native, result) -> InstallResult:
    staging = skills_dir / f".{target.name}{STAGE_MARKER}{uuid.uuid4().hex}"
    try:
        fsutil.copy_tree_regular(source, staging)
        if fault_hook:
            fault_hook("staged", target)
        if fsutil.tree_snapshot(staging) != source_hash:
            raise OSError("staged copy does not match the source")
        if fault_hook:
            fault_hook("before_publish", target)
        published = _publish(staging, target, native)
    except (OSError, fsutil.UnsafePathError) as exc:
        _cleanup(staging)
        return result(ERROR, f"install failed, nothing published: {exc}", EXIT_IO)
    except BaseException:
        _cleanup(staging)
        raise
    if published:
        fsutil.fsync_dir(skills_dir)
        return result(INSTALLED)
    _cleanup(staging)
    after = _inspect_existing(target, source_hash)
    return result(*(after or (BUSY, "destination changed during publication; retry")))


def _publish(staging: Path, target: Path, native: bool) -> bool:
    """Return True when published; False when the destination already exists."""
    if native:
        try:
            fsutil.rename_noreplace(staging, target)
            return True
        except FileExistsError:
            return False
        except fsutil.NoReplaceUnsupported:
            pass
    return _publish_with_reservation(staging, target)


def _publish_with_reservation(staging: Path, target: Path) -> bool:
    try:
        os.mkdir(target)
    except FileExistsError:
        return False
    try:
        os.rename(staging, target)  # replaces only an *empty* directory
        return True
    except OSError:
        # Someone wrote into our reservation; rmdir leaves it untouched if not empty.
        with contextlib.suppress(OSError):
            os.rmdir(target)
        return False


def _inspect_existing(target: Path, source_hash: dict) -> tuple[str, str] | None:
    if not os.path.lexists(target):
        return None
    if os.path.islink(target):
        return CONFLICT, "destination is a symlink; refusing to touch it"
    if not os.path.isdir(target):
        return CONFLICT, "destination exists and is not a directory"
    try:
        existing = fsutil.tree_snapshot(target)
    except fsutil.UnsafePathError as exc:
        return CONFLICT, f"destination contains unsupported entries: {exc}"
    except OSError as exc:
        return ERROR, f"cannot read destination: {exc}"
    if existing == source_hash:
        return ALREADY, ""
    if not existing:
        return BUSY, (
            "destination is an empty reservation (another install in progress or "
            "interrupted); retry or remove the empty directory"
        )
    return CONFLICT, (
        "destination differs from the canonical skill; it was left untouched "
        "(replacement is not supported in this release)"
    )


def _cleanup(staging: Path) -> None:
    # Only ever removes this operation's uniquely named staging directory.
    if STAGE_MARKER in staging.name and staging.exists() and not staging.is_symlink():
        shutil.rmtree(staging, ignore_errors=True)


def status_of(source: Path, target: Path) -> str:
    """Read-only comparison for doctor: missing | identical | differs | empty | unsafe."""
    if not os.path.lexists(target):
        return "missing"
    if os.path.islink(target) or not os.path.isdir(target):
        return "unsafe"
    try:
        existing = fsutil.tree_snapshot(target)
        if existing == fsutil.tree_snapshot(source):
            return "identical"
        return "differs" if existing else "empty"
    except (fsutil.UnsafePathError, OSError):
        return "unsafe"
