"""Copy-based, staged, no-replace installation of canonical skills.

Contract: docs/adr/0002-installation-safety.md. Existing destinations are never
deleted or modified; only this operation's staging directory is cleaned up.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

from engkit import fsutil, lockfile, platforms, sources
from engkit.errors import EXIT_BUSY, EXIT_CONFLICT, EXIT_FAILURE, EXIT_IO, EXIT_OK, EngkitError
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

# Statuses not listed here exit with EXIT_OK unless a result says otherwise.
STATUS_EXIT = {
    CONFLICT: EXIT_CONFLICT,
    BUSY: EXIT_BUSY,
    ERROR: EXIT_FAILURE,
    NOT_MANAGED: EXIT_FAILURE,
}
BUILTIN = {"source": "builtin", "ref": None, "path": None, "commit": None}
MODIFIED = (CONFLICT, "installed copy was modified; left untouched")
NOT_MANAGED_DETAIL = "no lock entry for this target; engkit did not install it"

STAGE_MARKER = ".engkit-stage-"

# Test seam called with (stage, destination path) at the named points of install and update.
fault_hook = None


def _hook(stage: str, path: Path) -> None:
    if fault_hook:
        fault_hook(stage, path)


@dataclass
class InstallResult:
    platform: str
    scope: str
    skill: str
    destination: Path
    status: str
    detail: str = ""
    exit_code: int | None = None

    def __post_init__(self):
        if self.exit_code is None:
            self.exit_code = STATUS_EXIT.get(self.status, EXIT_OK)

    def format(self) -> str:
        lines = [f"[{self.platform}] {self.skill}: {self.status} -> {self.destination}"]
        lines.extend(f"    {line}" for line in self.detail.split("\n") if self.detail)
        return "\n".join(fsutil.printable(line) for line in lines)


@dataclass(frozen=True)
class _Job:
    """A validated skill tree to copy; ``expected`` is the digest an installed copy must have."""

    root: Path
    name: str
    source: Path
    snapshot: dict
    native: bool
    expected: str = ""

    @property
    def new_digest(self) -> str:
        return lockfile.digest(self.snapshot)


@dataclass
class _UpdateRun:
    root: Path
    scope: str
    target: str
    resources: Path
    stack: contextlib.ExitStack
    cache: dict
    yes: bool
    native: bool


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


def _result(destination, name: str, status: str, detail: str = "", exit_code=None):
    path = destination.skill_path(name)
    scope, platform_id = destination.scope, destination.platform.id
    return InstallResult(platform_id, scope, name, path, status, detail, exit_code)


def _failures(platform_ids, scope, name, status, detail, exit_code=None) -> list[InstallResult]:
    return [
        InstallResult(platform_id, scope, name, Path("-"), status, detail, exit_code)
        for platform_id in platform_ids
    ]


def _validated(base: Path, containment: Path, name: str, label: str):
    """Return (skill path, content snapshot, problem); problem is empty when valid."""
    report = validate_dir(base, containment, name)
    errors = [issue.format() for issue in report.issues if issue.level == "error"]
    if errors or not report.skills:
        return None, {}, f"{label} failed validation: " + "; ".join(errors or ["unknown skill"])
    path = report.skills[0].path
    try:
        return path, fsutil.tree_snapshot(path), ""
    except (fsutil.UnsafePathError, OSError) as exc:
        return None, {}, str(exc)


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
    ids = [item.id for item in platforms.expand_target(target)]
    path, snapshot, problem = _validated(skills_dir, containment_root, name, "source")
    if problem:
        return _failures(ids, scope, name, ERROR, problem)
    try:
        root = resolve_root(scope, project_dir, home_dir)
    except OSError as exc:
        return _failures(ids, scope, name, ERROR, f"cannot resolve root: {exc}", EXIT_IO)
    lockfile.require_locking()
    fresh = {**origin, "content_sha256": lockfile.digest(snapshot), "targets": []}
    clash = _lock_clash(lockfile.read(root).get(name), fresh)
    if clash:
        return _failures(ids, scope, name, CONFLICT, clash)
    job = _Job(root, name, path, snapshot, allow_native_noreplace)
    results = []
    for platform_id in ids:
        destination = platforms.destination(platforms.get(platform_id), scope, root)
        results.append(_install_one(job, destination))
    done = [item.platform for item in results if item.status in (INSTALLED, ALREADY)]
    clash = _record(root, name, fresh, done) if done else ""
    for item in results:
        if clash and item.platform in done:
            item.status, item.exit_code = CONFLICT, EXIT_CONFLICT
            item.detail = f"{clash}; the copy was installed but is not recorded in the lock"
    return results


def _lock_clash(locked: dict | None, fresh: dict) -> str:
    if locked and (
        locked["source"] != fresh["source"] or locked["content_sha256"] != fresh["content_sha256"]
    ):
        return "locked from a different source or version; use update or uninstall first"
    return ""


def _record(root: Path, name: str, fresh: dict, done: list[str]) -> str:
    """Add ``done`` targets to the lock entry; return a clash message if another source won."""
    with lockfile.transaction(root) as skills:
        clash = _lock_clash(skills.get(name), fresh)
        if clash:
            return clash
        entry = skills.get(name) or fresh
        entry["targets"] = sorted({*entry["targets"], *done})
        skills[name] = entry
    return ""


def _install_one(job: _Job, destination: platforms.Destination) -> InstallResult:
    target = destination.skill_path(job.name)
    problems = fsutil.check_no_symlinks(destination.root, destination.parts)
    if problems:
        return _result(destination, job.name, ERROR, f"unsafe destination: {problems[0]}")
    # Cheap early answer; publication below re-checks atomically.
    early = _inspect_existing(target, job.snapshot)
    if early is not None:
        return _result(destination, job.name, *early)
    try:
        skills_dir = fsutil.ensure_real_dirs(destination.root, destination.parts)
    except fsutil.UnsafePathError as exc:
        return _result(destination, job.name, ERROR, f"unsafe destination: {exc}")
    except OSError as exc:
        detail = f"cannot create destination parents: {exc}"
        return _result(destination, job.name, ERROR, detail, EXIT_IO)
    return _stage_and_publish(job, destination, skills_dir)


def _stage_and_publish(job: _Job, destination, skills_dir: Path) -> InstallResult:
    target = destination.skill_path(job.name)
    staging = skills_dir / f".{target.name}{STAGE_MARKER}{uuid.uuid4().hex}"
    try:
        fsutil.copy_tree_regular(job.source, staging)
        _hook("staged", target)
        if fsutil.tree_snapshot(staging) != job.snapshot:
            raise OSError("staged copy does not match the source")
        _hook("before_publish", target)
        published = _publish(staging, target, job.native)
    except (OSError, fsutil.UnsafePathError) as exc:
        _cleanup(staging)
        detail = f"install failed, nothing published: {exc}"
        return _result(destination, job.name, ERROR, detail, EXIT_IO)
    except BaseException:
        _cleanup(staging)
        raise
    if published:
        fsutil.fsync_dir(skills_dir)
        return _result(destination, job.name, INSTALLED)
    _cleanup(staging)
    after = _inspect_existing(target, job.snapshot)
    return _result(destination, job.name, *(after or (BUSY, "destination changed; retry")))


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
    try:
        os.mkdir(target)  # reservation fallback
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


def _cleanup(staging: Path) -> None:
    # Only ever removes this operation's uniquely named staging directory.
    if STAGE_MARKER in staging.name and staging.exists() and not staging.is_symlink():
        shutil.rmtree(staging, ignore_errors=True)


def _read_tree(path: Path):
    """Return (snapshot, refusal) of a directory; the refusal is a (status, detail) pair."""
    if os.path.islink(path):
        return None, (CONFLICT, "destination is a symlink; refusing to touch it")
    if not os.path.isdir(path):
        return None, (CONFLICT, "destination exists and is not a directory")
    try:
        return fsutil.tree_snapshot(path), None
    except fsutil.UnsafePathError as exc:
        return None, (CONFLICT, f"destination contains unsupported entries: {exc}")
    except OSError as exc:
        return None, (ERROR, f"cannot read destination: {exc}")


def _inspect_existing(target: Path, source_hash: dict) -> tuple[str, str] | None:
    if not os.path.lexists(target):
        return None
    existing, refusal = _read_tree(target)
    if refusal:
        return refusal
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


def _tree_digest(path: Path) -> str:
    return lockfile.digest(fsutil.tree_snapshot(path))


def _installed_digest(destination: platforms.Destination, name: str):
    """Return (digest, refusal); the refusal is (status, detail) when the copy is unusable."""
    path = destination.skill_path(name)
    problems = fsutil.check_no_symlinks(destination.root, destination.parts)
    if problems:
        return "", (ERROR, f"unsafe destination: {problems[0]}")
    if not os.path.lexists(path):
        return "", (ERROR, "installed copy is missing")
    snapshot, refusal = _read_tree(path)
    return lockfile.digest(snapshot or {}), refusal


def _pristine_refusal(destination: platforms.Destination, name: str, expected: str):
    current, refusal = _installed_digest(destination, name)
    if not refusal and current != expected:
        return MODIFIED
    return refusal


def _staging_dir(root: Path) -> Path:
    staging = fsutil.ensure_real_dirs(root, (".engkit", "staging")) / uuid.uuid4().hex
    os.mkdir(staging)
    return staging


def _clear(staging: Path) -> str:
    """Delete a finished operation's staging directory; report it if that fails."""
    shutil.rmtree(staging, ignore_errors=True)
    if staging.exists():
        return f"could not delete {staging}; safe to delete manually"
    return ""


def _restore(old: Path, path: Path, new_digest: str, native: bool) -> bool:
    """Put the original back; only a path that hashes to our own new tree is removed."""
    try:
        occupied = os.path.lexists(path)
        if occupied and _tree_digest(path) != new_digest:
            return False
        if occupied:
            shutil.rmtree(path)
        return _publish(old, path, native)
    except (OSError, fsutil.UnsafePathError):
        return False


def _move_aside(path: Path, aside: Path, expected: str, stage: str, native: bool):
    """Move ``path`` to ``aside`` and re-hash it; if it changed meanwhile, put it back."""
    _hook(f"{stage}_checked", path)
    os.rename(path, aside)
    _hook(f"{stage}_moved", path)
    if _tree_digest(aside) == expected:
        return None
    detail = f"installed copy changed during {stage}; put back as it was"
    if not _publish(aside, path, native):
        detail = f"installed copy changed during {stage}; moved copy kept at {aside}"
    return CONFLICT, detail


def _exchange(job: _Job, destination: platforms.Destination, old: Path, new: Path):
    """Stage the new tree, move the old one aside and publish; return a refusal or None."""
    path = destination.skill_path(job.name)
    fsutil.copy_tree_regular(job.source, new)
    _hook("update_staged", path)
    if fsutil.tree_snapshot(new) != job.snapshot:
        raise OSError("staged copy does not match the source")
    refusal = _pristine_refusal(destination, job.name, job.expected)
    if refusal:
        return refusal
    refusal = _move_aside(path, old, job.expected, "update", job.native)
    if refusal:
        return refusal
    if not _publish(new, path, job.native):
        raise OSError("destination reappeared during update")
    _hook("update_published", path)
    if _tree_digest(path) != job.new_digest:
        raise OSError("published copy does not match the source")
    return None


def _swap(job: _Job, destination: platforms.Destination):
    """Replace the installed copy; return a refusal (status, detail) or None when done."""
    path = destination.skill_path(job.name)
    staging = _staging_dir(job.root)
    old = staging / "old"
    keep = False
    try:
        refusal = _exchange(job, destination, old, staging / "new")
        keep = bool(refusal) and os.path.lexists(old)
        return refusal
    except BaseException as exc:
        # Never delete staging while it may hold the only copy of the original.
        if os.path.lexists(old):
            keep = True  # stays set if _restore is itself interrupted
            keep = not _restore(old, path, job.new_digest, job.native)
        if keep and isinstance(exc, Exception):
            raise OSError(f"{exc}; original kept at {old}") from exc
        if keep:
            print(f"engkit: original kept at {old}", file=sys.stderr)
        raise
    finally:
        if not keep:
            shutil.rmtree(staging, ignore_errors=True)


def _update_target(job: _Job, destination: platforms.Destination) -> InstallResult:
    current, refusal = _installed_digest(destination, job.name)
    if not refusal and current == job.new_digest:
        return _result(destination, job.name, UP_TO_DATE)
    if not refusal and current != job.expected:
        refusal = MODIFIED
    try:
        refusal = refusal or _swap(job, destination)
    except (OSError, fsutil.UnsafePathError) as exc:
        detail = f"update failed, original kept: {exc}"
        return _result(destination, job.name, ERROR, detail, EXIT_IO)
    if refusal:
        return _result(destination, job.name, *refusal)
    return _result(destination, job.name, UPDATED)


def _uninstall_target(root: Path, destination, name: str, expected: str) -> InstallResult:
    refusal = _pristine_refusal(destination, name, expected)
    if refusal:
        return _result(destination, name, *refusal)
    try:
        staging = _staging_dir(root)
    except OSError as exc:
        return _result(destination, name, ERROR, f"uninstall failed: {exc}", EXIT_IO)
    removed = staging / "removed"
    path = destination.skill_path(name)
    try:
        refusal = _move_aside(path, removed, expected, "uninstall", True)
    except BaseException as exc:
        if not (os.path.lexists(removed) and not _publish(removed, path, True)):
            shutil.rmtree(staging, ignore_errors=True)
        if not isinstance(exc, (OSError, fsutil.UnsafePathError)):
            raise
        return _result(destination, name, ERROR, f"uninstall failed: {exc}", EXIT_IO)
    if refusal:
        if not os.path.lexists(removed):
            shutil.rmtree(staging, ignore_errors=True)
        return _result(destination, name, *refusal)
    return _result(destination, name, UNINSTALLED, _clear(staging))


def _split(entry: dict | None, target: str) -> tuple[list[str], list[str]]:
    """Return (locked platform ids, requested ids without a lock entry)."""
    locked = entry["targets"] if entry else []
    requested = [item.id for item in platforms.expand_target(target)]
    managed = [item for item in requested if item in locked]
    if target == "all" and managed:
        return managed, []
    return managed, [item for item in requested if item not in managed]


def _destination(root: Path, scope: str, platform_id: str) -> platforms.Destination:
    return platforms.destination(platforms.get(platform_id), scope, root)


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
        ids = [item.id for item in platforms.expand_target(target)]
        return _failures(ids, scope, name, NOT_MANAGED, NOT_MANAGED_DETAIL)
    with lockfile.transaction(root) as skills:
        entry = skills.get(name)
        managed, unmanaged = _split(entry, target)
        results = _failures(unmanaged, scope, name, NOT_MANAGED, NOT_MANAGED_DETAIL)
        for platform_id in managed:
            destination = _destination(root, scope, platform_id)
            results.append(_uninstall_target(root, destination, name, entry["content_sha256"]))
        gone = {item.platform for item in results if item.status == UNINSTALLED}
        if entry is not None:
            entry["targets"] = [item for item in entry["targets"] if item not in gone]
        if entry is not None and not entry["targets"]:
            del skills[name]
    return results


def _preview(header: list[str], base: Path, containment: Path, names: list[str], scope: str):
    problems = []
    for name in names:
        problem = _validated(base, containment, name, "source")[2]
        if problem:
            problems.append(problem)
    label = ",".join(names)
    if problems:
        return InstallResult("-", scope, label, Path("-"), ERROR, "; ".join(problems))
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
        options = {"scope": scope, "project_dir": project_dir, "home_dir": home_dir}
        results = []
        for name in names:
            batch = install_dir(base, fetched.root, name, target, origin=origin, **options)
            results += _stamp_commit(batch, fetched.commit)
    return results


def _stamp_commit(results: list[InstallResult], commit: str) -> list[InstallResult]:
    for item in results:
        item.detail = item.detail or f"commit {commit}"
    return results


def _new_source(entry: dict, run: _UpdateRun):
    """Return (skills dir, containment root, commit) of the entry's current upstream."""
    if entry["source"] == "builtin":
        return run.resources / "skills", run.resources, None
    key = (entry["source"], entry["ref"], entry["path"])
    if key not in run.cache:
        run.cache[key] = run.stack.enter_context(sources.fetch(*key))
    fetched = run.cache[key]
    return sources.skills_dir(fetched.root, entry["path"]), fetched.root, fetched.commit


def _wants_confirmation(entry: dict, snapshot: dict, yes: bool) -> bool:
    if entry["source"] == "builtin" or yes:
        return False
    return lockfile.digest(snapshot) != entry["content_sha256"]


def _update_name(run: _UpdateRun, name: str) -> list[InstallResult]:
    entry = lockfile.read(run.root).get(name)
    managed, unmanaged = _split(entry, run.target)
    if not managed:
        return _failures(unmanaged, run.scope, name, NOT_MANAGED, NOT_MANAGED_DETAIL)
    left_out = [item for item in entry["targets"] if item not in managed]
    if left_out:
        detail = (
            f"updating only {', '.join(managed)} would leave {', '.join(left_out)} on the old "
            "content; update all targets of this skill together (--target all)"
        )
        return _failures(managed, run.scope, name, ERROR, detail)
    base, containment, commit = _new_source(entry, run)
    path, snapshot, problem = _validated(base, containment, name, "upstream")
    if problem:
        return _failures(managed, run.scope, name, ERROR, problem)
    if _wants_confirmation(entry, snapshot, run.yes):
        header = [f"source: {sources.redact(entry['source'])}", f"ref: {entry['ref'] or 'HEAD'}"]
        header.append(f"{name}: {entry['commit']} -> {commit}")
        return [_preview(header, base, containment, [name], run.scope)]
    job = _Job(run.root, name, path, snapshot, run.native, entry["content_sha256"])
    return _apply_updates(run, job, managed, commit)


def _blocked_targets(job: _Job, destinations: list) -> list[InstallResult]:
    """Results refusing the whole update when any target is not pristine; else an empty list."""
    refusals = []
    for destination in destinations:
        current, refusal = _installed_digest(destination, job.name)
        if not refusal and current not in (job.expected, job.new_digest):
            refusal = MODIFIED
        refusals.append(refusal)
    if not any(refusals):
        return []
    skipped = (CONFLICT, "skipped (another target is modified)")
    return [
        _result(destination, job.name, *(refusal or skipped))
        for destination, refusal in zip(destinations, refusals, strict=True)
    ]


def _apply_updates(run: _UpdateRun, job: _Job, managed: list[str], commit) -> list:
    with lockfile.transaction(run.root) as skills:
        locked = skills[job.name]
        job = replace(job, expected=locked["content_sha256"])
        destinations = [_destination(run.root, run.scope, item) for item in managed]
        blocked = _blocked_targets(job, destinations)
        if blocked:
            return blocked
        results = [_update_target(job, destination) for destination in destinations]
        current = {item.platform for item in results if item.status in (UPDATED, UP_TO_DATE)}
        # Unchanged content with a moved commit is only recorded on an explicit --yes.
        if current == set(locked["targets"]) and (run.yes or commit is None):
            locked.update(content_sha256=job.new_digest, commit=commit)
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
    with contextlib.ExitStack() as stack:
        run = _UpdateRun(root, scope, target, resources, stack, {}, yes, allow_native_noreplace)
        for name in selected:
            results += _update_name_reporting(run, name)
    return results


def _update_name_reporting(run: _UpdateRun, name: str) -> list[InstallResult]:
    """Update one skill; a failure (such as a failed fetch) becomes its own error result."""
    try:
        return _update_name(run, name)
    except EngkitError as exc:
        ids = [item.id for item in platforms.expand_target(run.target)]
        return _failures(ids, run.scope, name, ERROR, str(exc), exc.exit_code)


def status_of(source: Path, target: Path) -> str:
    """Read-only comparison for doctor: missing | identical | differs | empty | unsafe."""
    if not os.path.lexists(target):
        return "missing"
    existing, refusal = _read_tree(target)
    if refusal:
        return "unsafe"
    try:
        if existing == fsutil.tree_snapshot(source):
            return "identical"
    except (fsutil.UnsafePathError, OSError):
        return "unsafe"
    if not existing:
        return "empty"
    return "differs"
