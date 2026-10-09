"""Standard-library filesystem helpers; nothing here executes files."""

from __future__ import annotations

import contextlib
import ctypes
import ctypes.util
import errno
import hashlib
import os
import stat
import sys
from pathlib import Path

NAME_MAX = 64


class UnsafePathError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def safe_relpath(value: str, what: str = "path") -> str:
    """Validate a project-relative POSIX path: no absolute, no '..', no empty parts."""
    if not isinstance(value, str) or not value:
        raise UnsafePathError(f"{what} must be a non-empty relative path")
    if "\\" in value or "\x00" in value:
        raise UnsafePathError(f"{what} {value!r} contains a backslash or NUL")
    if value.startswith("/") or (len(value) > 1 and value[1] == ":"):
        raise UnsafePathError(f"{what} {value!r} must be relative")
    if value == ".":
        return "."
    parts = value.split("/")
    if "" in parts or ".." in parts or "." in parts:
        raise UnsafePathError(f"{what} {value!r} must not contain '.', '..' or empty segments")
    return value


def _raise_walk_error(exc: OSError) -> None:
    # os.walk ignores errors by default, which would hide unreadable directories.
    raise exc


def _walk(root: Path):
    return os.walk(root, followlinks=False, onerror=_raise_walk_error)


def _symlink_marker(path: Path) -> str:
    return f"<symlink:{os.readlink(path)}>"


def _snapshot_directories(
    base: Path, rel_base: str, dirnames: list[str], allow_symlinks: bool, result: dict[str, str]
) -> None:
    for name in sorted(dirnames):
        path = base / name
        if not path.is_symlink():
            continue
        if not allow_symlinks:
            raise UnsafePathError(f"refusing symlink: {path}")
        result[_join(rel_base, name)] = _symlink_marker(path)
    dirnames[:] = sorted(name for name in dirnames if not (base / name).is_symlink())


def _snapshot_files(
    base: Path, rel_base: str, filenames: list[str], allow_symlinks: bool, result: dict[str, str]
) -> None:
    for name in sorted(filenames):
        path = base / name
        mode = os.lstat(path).st_mode
        if stat.S_ISLNK(mode):
            if not allow_symlinks:
                raise UnsafePathError(f"refusing symlink: {path}")
            result[_join(rel_base, name)] = _symlink_marker(path)
        elif stat.S_ISREG(mode):
            result[_join(rel_base, name)] = sha256_file(path)
        else:
            raise UnsafePathError(f"refusing special file: {path}")


def tree_snapshot(root: Path, *, allow_symlinks: bool = False) -> dict[str, str]:
    """Map relative POSIX path to sha256 for every regular file below ``root``.

    Empty directories are recorded as "<dir>". Symlinks and special files raise
    UnsafePathError unless ``allow_symlinks`` (then recorded without being followed).
    """
    result: dict[str, str] = {}
    for dirpath, dirnames, filenames in _walk(root):
        base = Path(dirpath)
        rel_base = base.relative_to(root).as_posix()
        _snapshot_directories(base, rel_base, dirnames, allow_symlinks, result)
        if not dirnames and not filenames and base != root:
            result[rel_base] = "<dir>"
        _snapshot_files(base, rel_base, filenames, allow_symlinks, result)
    return result


def _join(rel_base: str, name: str) -> str:
    return name if rel_base == "." else f"{rel_base}/{name}"


def copy_tree_regular(src: Path, dst: Path) -> None:
    """Copy regular files and directories only; ``dst`` must not exist."""
    os.mkdir(dst)
    for dirpath, dirnames, filenames in _walk(src):
        base = Path(dirpath)
        out = dst / base.relative_to(src)
        for name in sorted(dirnames):
            if (base / name).is_symlink():
                raise UnsafePathError(f"refusing symlink: {base / name}")
            os.mkdir(out / name)
        for name in sorted(filenames):
            path = base / name
            mode = os.lstat(path).st_mode
            if not stat.S_ISREG(mode):
                raise UnsafePathError(f"refusing non-regular file: {path}")
            write_file(out / name, path.read_bytes(), exclusive=True, mode=mode & 0o777)


def write_file(path: Path, data: bytes, *, exclusive: bool = True, mode: int = 0o644) -> None:
    """Write bytes and fsync; ``exclusive`` refuses to replace an existing path."""
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, mode)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        with contextlib.suppress(OSError):
            os.fsync(fd)
    finally:
        os.close(fd)


def ensure_real_dirs(root: Path, rel_parts: tuple[str, ...]) -> Path:
    """Create ``root/parts...`` refusing symlinks; ``root`` must already be resolved."""
    # mkdir then lstat per part (not makedirs) so a symlink planted between steps is caught.
    current = root
    for part in rel_parts:
        current = current / part
        with contextlib.suppress(FileExistsError):
            os.mkdir(current)
        mode = os.lstat(current).st_mode
        if stat.S_ISLNK(mode):
            raise UnsafePathError(f"refusing symlinked directory: {current}")
        if not stat.S_ISDIR(mode):
            raise UnsafePathError(f"not a directory: {current}")
    if os.path.realpath(current) != str(current):
        raise UnsafePathError(f"directory resolves outside its expected location: {current}")
    return current


def check_no_symlinks(root: Path, rel_parts: tuple[str, ...]) -> list[str]:
    """Read-only variant of ensure_real_dirs: report problems without creating anything."""
    current = root
    for part in rel_parts:
        current = current / part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            return []
        if stat.S_ISLNK(mode):
            return [f"symlinked path: {current}"]
        if not stat.S_ISDIR(mode):
            return [f"not a directory: {current}"]
    return []


class NoReplaceUnsupported(OSError):
    pass


_libc = None
_RENAME_EXCL = 0x00000004  # macOS renamex_np flag
_AT_FDCWD = -100
_RENAME_NOREPLACE = 1  # Linux renameat2 flag


def _get_libc():
    global _libc
    if _libc is None:
        name = ctypes.util.find_library("c")
        _libc = ctypes.CDLL(name, use_errno=True) if name else False
    return _libc or None


def rename_noreplace(src: Path, dst: Path) -> None:
    """Atomically rename; raises FileExistsError if ``dst`` exists."""
    libc = _get_libc()
    source, destination = os.fsencode(src), os.fsencode(dst)
    if libc is not None and sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        if libc.renamex_np(source, destination, _RENAME_EXCL) == 0:
            return
        _raise_rename_error(ctypes.get_errno(), src, dst)
    if libc is not None and sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        if libc.renameat2(_AT_FDCWD, source, _AT_FDCWD, destination, _RENAME_NOREPLACE) == 0:
            return
        _raise_rename_error(ctypes.get_errno(), src, dst)
    raise NoReplaceUnsupported(errno.ENOSYS, "no-replace rename is not available on this platform")


def _raise_rename_error(err: int, src: Path, dst: Path) -> None:
    unsupported = (errno.ENOSYS, errno.EINVAL, errno.ENOTSUP, getattr(errno, "EOPNOTSUPP", 0))
    if err in (errno.EEXIST, errno.ENOTEMPTY):
        raise FileExistsError(err, os.strerror(err), str(dst))
    if err in unsupported:
        raise NoReplaceUnsupported(err, os.strerror(err), str(dst))
    raise OSError(err, os.strerror(err), str(src))


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True
