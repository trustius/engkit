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

from engkit import fsutil, lockfile, platforms, sources
from engkit.errors import EXIT_BUSY, EXIT_CONFLICT, EXIT_FAILURE, EXIT_IO, EXIT_OK
from engkit.validator import validate_dir

INSTALLED = "installed"
ALREADY = "already installed"
CONFLICT = "conflict"
BUSY = "busy"
ERROR = "error"
UPDATED = "updated"
UP_TO_DATE = "up to date"
UNINSTALLED = "uninstalled"
NOT_MANAGED = "not managed"
PREVIEW = "preview"

STATUS_EXIT = {
    INSTALLED: EXIT_OK,
    ALREADY: EXIT_OK,
    UPDATED: EXIT_OK,
    UP_TO_DATE: EXIT_OK,
    UNINSTALLED: EXIT_OK,
    PREVIEW: EXIT_OK,
    CONFLICT: EXIT_CONFLICT,
    BUSY: EXIT_BUSY,
}
BUILTIN = {"source": "builtin", "ref": None, "path": None, "commit": None}

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
        if not self.detail:
            return line
        return line + "\n    " + self.detail.replace("\n", "\n    ")


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
    targets: list[platforms.Platform],
    scope: str,
    name: str,
    detail: str,
    exit_code: int,
    status: str = ERROR,
) -> list[InstallResult]:
    return [
        InstallResult(item.id, scope, name, Path("-"), status, detail, exit_code)
        for item in targets
    ]


def install(toolkit_root: Path, name: str, target: str, **options) -> list[InstallResult]:
    """Install one built-in skill from ``toolkit_root/skills``."""
    return install_dir(toolkit_root / "skills", toolkit_root, name, target, **options)


def install_dir(
    skills_dir: Path,
    containment_root: Path,
    name: str,
    target: str,
    *,
    scope: str = "project",
    project_dir: str | os.PathLike | None = None,
    home_dir: str | os.PathLike | None = None,
    allow_native_noreplace: bool = True,
    origin: dict = BUILTIN,
) -> list[InstallResult]:
    """Install one skill to each requested platform and record it in the lock."""
    targets = platforms.expand_target(target)
    report = validate_dir(skills_dir, containment_root, name)
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
    content = lockfile.digest(source_hash)
    clash = _lock_clash(lockfile.read(root).get(name), origin, content)
    if clash:
        return _failures(targets, scope, name, clash, EXIT_CONFLICT, CONFLICT)
    results = []
    for platform in targets:
        destination = platforms.destination(platform, scope, root)
        results.append(_install_one(source, source_hash, name, destination, allow_native_noreplace))
    done = [item.platform for item in results if item.status in (INSTALLED, ALREADY)]
    if done:
        _record(root, name, {**origin, "content_sha256": content, "targets": []}, done)
    return results


def _lock_clash(locked: dict | None, origin: dict, content: str) -> str:
    if locked and (locked["source"] != origin["source"] or locked["content_sha256"] != content):
        return "locked from a different source or version; use update or uninstall first"
    return ""


def _record(root: Path, name: str, fresh: dict, done: list[str]) -> None:
    with lockfile.transaction(root) as skills:
        entry = skills.get(name) or fresh
        entry["targets"] = sorted({*entry["targets"], *done})
        skills[name] = entry


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


class _Refused(Exception):
    def __init__(self, status: str, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def _result(destination, name: str, status: str, detail: str = "", code=None) -> InstallResult:
    exit_code = STATUS_EXIT.get(status, EXIT_FAILURE) if code is None else code
    path = destination.skill_path(name)
    return InstallResult(
        destination.platform.id, destination.scope, name, path, status, detail, exit_code
    )


def _unmanaged(name: str, ids: list[str], scope: str) -> list[InstallResult]:
    detail = "no lock entry for this target; engkit did not install it"
    return [
        InstallResult(item, scope, name, Path("-"), NOT_MANAGED, detail, EXIT_FAILURE)
        for item in ids
    ]


def _split(locked_targets: list[str], target: str) -> tuple[list[str], list[str]]:
    """Return (locked platform ids, requested ids without a lock entry)."""
    requested = [item.id for item in platforms.expand_target(target)]
    managed = [item for item in requested if item in locked_targets]
    if target == "all" and managed:
        return managed, []
    return managed, [item for item in requested if item not in managed]


def _destination(root: Path, scope: str, platform_id: str) -> platforms.Destination:
    return platforms.destination(platforms.get(platform_id), scope, root)


def _current_digest(destination: platforms.Destination, name: str) -> str:
    path = destination.skill_path(name)
    problems = fsutil.check_no_symlinks(destination.root, destination.parts)
    if problems:
        raise _Refused(ERROR, f"unsafe destination: {problems[0]}")
    if not os.path.lexists(path):
        raise _Refused(ERROR, "installed copy is missing")
    if os.path.islink(path) or not os.path.isdir(path):
        raise _Refused(CONFLICT, "installed path is not a regular directory; left untouched")
    try:
        return lockfile.digest(fsutil.tree_snapshot(path))
    except fsutil.UnsafePathError as exc:
        raise _Refused(CONFLICT, f"installed copy has unsupported entries: {exc}") from None


def _staging_dir(root: Path) -> Path:
    staging = fsutil.ensure_real_dirs(root, (".engkit", "staging")) / uuid.uuid4().hex
    os.mkdir(staging)
    return staging


def _restore(old: Path, path: Path, new_digest: str, native: bool) -> bool:
    """Put the original back; only a path that hashes to our own new tree is removed."""
    try:
        if os.path.lexists(path):
            if lockfile.digest(fsutil.tree_snapshot(path)) != new_digest:
                return False
            shutil.rmtree(path)
        return _publish(old, path, native)
    except (OSError, fsutil.UnsafePathError):
        return False


def _swap(root, destination, name, source, snapshot, old_digest, native) -> None:
    path = destination.skill_path(name)
    new_digest = lockfile.digest(snapshot)
    staging = _staging_dir(root)
    keep = False
    try:
        fsutil.copy_tree_regular(source, staging / "new")
        if fault_hook:
            fault_hook("update_staged", path)
        if fsutil.tree_snapshot(staging / "new") != snapshot:
            raise OSError("staged copy does not match the source")
        if _current_digest(destination, name) != old_digest:
            raise _Refused(CONFLICT, "installed copy changed during update; left untouched")
        os.rename(path, staging / "old")
        try:
            if not _publish(staging / "new", path, native):
                raise OSError("destination reappeared during update")
            if fault_hook:
                fault_hook("update_published", path)
            if lockfile.digest(fsutil.tree_snapshot(path)) != new_digest:
                raise OSError("published copy does not match the source")
        except BaseException as exc:
            keep = not _restore(staging / "old", path, new_digest, native)
            if keep:
                raise OSError(f"{exc}; original kept at {staging / 'old'}") from exc
            raise
    finally:
        if not keep:
            shutil.rmtree(staging, ignore_errors=True)


def _update_target(root, destination, name, source, snapshot, old_digest, native):
    try:
        current = _current_digest(destination, name)
        if current == lockfile.digest(snapshot):
            return _result(destination, name, UP_TO_DATE)
        if current != old_digest:
            raise _Refused(CONFLICT, "installed copy was modified; left untouched")
        _swap(root, destination, name, source, snapshot, old_digest, native)
    except _Refused as refused:
        return _result(destination, name, refused.status, refused.detail)
    except (OSError, fsutil.UnsafePathError) as exc:
        return _result(destination, name, ERROR, f"update failed, original kept: {exc}", EXIT_IO)
    return _result(destination, name, UPDATED)


def _uninstall_target(root, destination, name, digest):
    try:
        if _current_digest(destination, name) != digest:
            raise _Refused(CONFLICT, "installed copy was modified; left untouched")
        staging = _staging_dir(root)
        os.rename(destination.skill_path(name), staging / "removed")
        shutil.rmtree(staging)
    except _Refused as refused:
        return _result(destination, name, refused.status, refused.detail)
    except OSError as exc:
        return _result(destination, name, ERROR, f"uninstall failed: {exc}", EXIT_IO)
    return _result(destination, name, UNINSTALLED)


def uninstall(
    name: str,
    target: str,
    *,
    scope: str = "project",
    project_dir: str | os.PathLike | None = None,
    home_dir: str | os.PathLike | None = None,
) -> list[InstallResult]:
    """Remove a pristine installed copy and drop it from the lock."""
    root = resolve_root(scope, project_dir, home_dir)
    if name not in lockfile.read(root):
        return _unmanaged(name, [item.id for item in platforms.expand_target(target)], scope)
    with lockfile.transaction(root) as skills:
        entry = skills.get(name)
        managed, unmanaged = _split(entry["targets"] if entry else [], target)
        results = _unmanaged(name, unmanaged, scope)
        for platform_id in managed:
            destination = _destination(root, scope, platform_id)
            results.append(_uninstall_target(root, destination, name, entry["content_sha256"]))
        gone = {item.platform for item in results if item.status == UNINSTALLED}
        entry["targets"] = [item for item in entry["targets"] if item not in gone]
        if not entry["targets"]:
            del skills[name]
    return results


def _preview(header: list[str], base: Path, containment: Path, names: list[str], scope: str):
    problems = []
    for name in names:
        report = validate_dir(base, containment, name)
        problems += [issue.format() for issue in report.issues if issue.level == "error"]
    label = ",".join(names)
    if problems:
        detail = "source failed validation: " + "; ".join(problems)
        return InstallResult("-", scope, label, Path("-"), ERROR, detail, EXIT_FAILURE)
    text = sources.preview_text(header, base, names, ["validation: ok"])
    return InstallResult("-", scope, label, Path("-"), PREVIEW, text)


def install_remote(
    url: str,
    ref: str | None,
    path: str | None,
    names: list[str],
    target: str,
    *,
    scope: str = "project",
    project_dir: str | os.PathLike | None = None,
    home_dir: str | os.PathLike | None = None,
    yes: bool = False,
) -> list[InstallResult]:
    """Install skills from a git source; without ``yes`` only a preview is produced."""
    with sources.fetch(url, ref, path) as fetched:
        base = sources.skills_dir(fetched.root, path)
        if not yes:
            header = [
                f"source: {sources.redact(url)}",
                f"ref: {ref or 'HEAD'}",
                f"commit: {fetched.commit}",
            ]
            return [_preview(header, base, fetched.root, names, scope)]
        origin = {"source": url, "ref": ref, "path": path, "commit": fetched.commit}
        results = []
        for name in names:
            options = {"scope": scope, "project_dir": project_dir, "home_dir": home_dir}
            batch = install_dir(base, fetched.root, name, target, origin=origin, **options)
            for item in batch:
                item.detail = item.detail or f"commit {fetched.commit}"
            results += batch
    return results


def _new_source(entry: dict, resources: Path, stack, cache: dict):
    """Return (skills dir, containment root, commit) of the entry's current upstream."""
    if entry["source"] == "builtin":
        return resources / "skills", resources, None
    key = (entry["source"], entry["ref"], entry["path"])
    if key not in cache:
        cache[key] = stack.enter_context(sources.fetch(*key))
    fetched = cache[key]
    return sources.skills_dir(fetched.root, entry["path"]), fetched.root, fetched.commit


def _update_name(root, scope, name, target, resources, stack, cache, yes, native):
    entry = lockfile.read(root).get(name)
    managed, unmanaged = _split(entry["targets"] if entry else [], target)
    if not managed:
        return _unmanaged(name, unmanaged, scope)
    base, containment, commit = _new_source(entry, resources, stack, cache)
    report = validate_dir(base, containment, name)
    errors = [issue.format() for issue in report.issues if issue.level == "error"]
    if errors or not report.skills:
        detail = "upstream failed validation: " + "; ".join(errors or ["unknown skill"])
        return _failures(platforms.expand_target(target), scope, name, detail, EXIT_FAILURE)
    snapshot = fsutil.tree_snapshot(report.skills[0].path)
    if (
        entry["source"] != "builtin"
        and not yes
        and lockfile.digest(snapshot) != entry["content_sha256"]
    ):
        header = [f"source: {sources.redact(entry['source'])}", f"ref: {entry['ref'] or 'HEAD'}"]
        header.append(f"{name}: {entry['commit']} -> {commit}")
        return [_preview(header, base, containment, [name], scope)]
    return _apply_updates(
        root, scope, name, (managed, unmanaged), report.skills[0].path, snapshot, commit, native
    )


def _apply_updates(root, scope, name, split, source, snapshot, commit, native):
    managed, unmanaged = split
    with lockfile.transaction(root) as skills:
        locked = skills[name]
        results = _unmanaged(name, unmanaged, scope)
        for platform_id in managed:
            destination = _destination(root, scope, platform_id)
            args = (root, destination, name, source, snapshot, locked["content_sha256"], native)
            results.append(_update_target(*args))
        current = {item.platform for item in results if item.status in (UPDATED, UP_TO_DATE)}
        if current == set(locked["targets"]):
            locked.update(content_sha256=lockfile.digest(snapshot), commit=commit)
    return results


def update(
    resources: Path,
    names: list[str],
    target: str = "all",
    *,
    scope: str = "project",
    project_dir: str | os.PathLike | None = None,
    home_dir: str | os.PathLike | None = None,
    yes: bool = False,
    allow_native_noreplace: bool = True,
) -> list[InstallResult]:
    """Update locked skills (all when ``names`` is empty) that are still pristine."""
    root = resolve_root(scope, project_dir, home_dir)
    selected = names or sorted(lockfile.read(root))
    results = []
    cache: dict = {}
    with contextlib.ExitStack() as stack:
        for name in selected:
            args = (root, scope, name, target, resources, stack, cache, yes)
            results += _update_name(*args, allow_native_noreplace)
    return results


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
