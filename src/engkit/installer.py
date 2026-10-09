"""Copy-based, staged, no-replace installation of canonical skills.

Contract (docs/adr/0002-installation-safety.md):
1. Validate the canonical source.
2. Resolve the root once; create/verify each managed parent below it,
   refusing symlinks and non-directories.
3. Copy into an operation-owned staging sibling, verify against the source hash.
4. Publish with an atomic no-replace rename (renamex_np / renameat2). Where
   unavailable, use the reservation protocol: ``mkdir(dest)`` (exclusive) then
   rename staging onto the still-empty reserved directory; a non-empty
   reservation makes the rename fail rather than replace content.
5. If the destination already exists, compare it: identical -> already
   installed, empty reservation -> busy, otherwise -> conflict. Existing
   destinations are never deleted or modified.
6. Clean only this operation's staging directory.
"""

from __future__ import annotations

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

# Test seam: called with a stage name ("staged", "before_publish") and the
# destination path. Production code leaves it as None.
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


def resolve_root(scope: str, project_dir: str | os.PathLike | None, home_dir: str | os.PathLike | None) -> Path:
    if scope == "project":
        raw = Path(project_dir) if project_dir is not None else Path.cwd()
    else:
        raw = Path(home_dir) if home_dir is not None else Path.home()
    root = raw.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")
    return root


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
    """Install one skill to each requested platform. Returns per-target results."""
    targets = platforms.expand_target(target)
    report = validate(toolkit_root, name)
    errors = [i for i in report.issues if i.level == "error"]
    if errors or not report.skills:
        detail = "; ".join(i.format() for i in errors) or "unknown skill"
        return [
            InstallResult(p.id, scope, name, Path("-"), ERROR, f"source failed validation: {detail}", EXIT_FAILURE)
            for p in targets
        ]
    source = report.skills[0].path
    try:
        source_hash = fsutil.tree_snapshot(source, allow_symlinks=False)
    except fsutil.UnsafePathError as exc:
        return [InstallResult(p.id, scope, name, Path("-"), ERROR, str(exc), EXIT_FAILURE) for p in targets]
    try:
        root = resolve_root(scope, project_dir, home_dir)
    except OSError as exc:
        return [InstallResult(p.id, scope, name, Path("-"), ERROR, f"cannot resolve root: {exc}", EXIT_IO) for p in targets]

    results = []
    for platform in targets:
        dest = platforms.destination(platform, scope, root)
        results.append(_install_one(source, source_hash, name, dest, allow_native_noreplace))
    return results


def _install_one(source: Path, source_hash: dict, name: str, dest: platforms.Destination, native: bool) -> InstallResult:
    target = dest.skill_path(name)

    def result(status: str, detail: str = "", code: int | None = None) -> InstallResult:
        return InstallResult(dest.platform.id, dest.scope, name, target, status, detail,
                             STATUS_EXIT.get(status, EXIT_FAILURE) if code is None else code)

    # Cheap early answer; publication below re-checks atomically.
    early = _inspect_existing(target, source_hash)
    if early is not None:
        return result(*early)
    try:
        skills_dir = fsutil.ensure_real_dirs(dest.root, dest.parts)
    except fsutil.UnsafePathError as exc:
        return result(ERROR, f"unsafe destination: {exc}", EXIT_FAILURE)
    except OSError as exc:
        return result(ERROR, f"cannot create destination parents: {exc}", EXIT_IO)

    staging = skills_dir / f".{name}{STAGE_MARKER}{uuid.uuid4().hex}"
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
    # Reservation protocol: exclusive mkdir, then rename onto the empty reservation.
    try:
        os.mkdir(target)
    except FileExistsError:
        return False
    try:
        os.rename(staging, target)  # replaces only an *empty* directory
        return True
    except OSError:
        # Someone wrote into our reservation; leave it untouched if not empty.
        try:
            os.rmdir(target)
        except OSError:
            pass
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
        return BUSY, "destination is an empty reservation (another install in progress or interrupted); retry or remove the empty directory"
    return CONFLICT, "destination differs from the canonical skill; it was left untouched (replacement is not supported in this release)"


def _cleanup(staging: Path) -> None:
    # Only ever removes this operation's uniquely named staging directory.
    if STAGE_MARKER in staging.name and staging.exists() and not staging.is_symlink():
        shutil.rmtree(staging, ignore_errors=True)


def status_of(source: Path, target: Path) -> str:
    """Read-only comparison used by doctor: missing | identical | differs | unsafe."""
    if not os.path.lexists(target):
        return "missing"
    if os.path.islink(target) or not os.path.isdir(target):
        return "unsafe"
    try:
        same = fsutil.tree_snapshot(target) == fsutil.tree_snapshot(source)
    except (fsutil.UnsafePathError, OSError):
        return "unsafe"
    if same:
        return "identical"
    return "empty" if not any(target.iterdir()) else "differs"
