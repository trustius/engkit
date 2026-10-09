"""Filesystem helpers shared by the installer and generator.

Everything here uses the standard library only and never executes files.
"""

from __future__ import annotations

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
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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
    parts = value.split("/")
    if value == ".":
        return "."
    if any(p in ("", "..") for p in parts) or "." in parts:
        raise UnsafePathError(f"{what} {value!r} must not contain '.', '..' or empty segments")
    return value


def tree_snapshot(root: Path, *, allow_symlinks: bool = False) -> dict[str, str]:
    """Map relative POSIX path -> sha256 for every regular file below ``root``.

    Directories are implied by their files; empty directories are recorded with
    the marker ``"<dir>"`` so they participate in comparisons. Symlinks and
    special files raise UnsafePathError unless ``allow_symlinks`` (then they
    are recorded as ``"<symlink:target>"`` without being followed).
    """
    result: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(dirpath)
        rel_base = base.relative_to(root).as_posix()
        for name in sorted(dirnames):
            p = base / name
            if p.is_symlink():
                if not allow_symlinks:
                    raise UnsafePathError(f"refusing symlink: {p}")
                result[_join(rel_base, name)] = f"<symlink:{os.readlink(p)}>"
        dirnames[:] = sorted(d for d in dirnames if not (base / d).is_symlink())
        if not dirnames and not filenames and base != root:
            result[rel_base] = "<dir>"
        for name in sorted(filenames):
            p = base / name
            st = os.lstat(p)
            if stat.S_ISLNK(st.st_mode):
                if not allow_symlinks:
                    raise UnsafePathError(f"refusing symlink: {p}")
                result[_join(rel_base, name)] = f"<symlink:{os.readlink(p)}>"
                continue
            if not stat.S_ISREG(st.st_mode):
                raise UnsafePathError(f"refusing special file: {p}")
            result[_join(rel_base, name)] = sha256_file(p)
    return result


def _join(rel_base: str, name: str) -> str:
    return name if rel_base == "." else f"{rel_base}/{name}"


def copy_tree_regular(src: Path, dst: Path) -> None:
    """Copy regular files and directories only. ``dst`` must not exist.

    Symlinks and special files are refused (callers validate sources first).
    """
    os.mkdir(dst)
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        base = Path(dirpath)
        out = dst / base.relative_to(src)
        for name in sorted(dirnames):
            if (base / name).is_symlink():
                raise UnsafePathError(f"refusing symlink: {base / name}")
            os.mkdir(out / name)
        for name in sorted(filenames):
            p = base / name
            st = os.lstat(p)
            if not stat.S_ISREG(st.st_mode):
                raise UnsafePathError(f"refusing non-regular file: {p}")
            write_file(out / name, p.read_bytes(), exclusive=True, mode=st.st_mode & 0o777)


def write_file(path: Path, data: bytes, *, exclusive: bool = True, mode: int = 0o644) -> None:
    """Write bytes and fsync. ``exclusive`` refuses to replace an existing path."""
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, mode)
    try:
        view = memoryview(data)
        while view:
            n = os.write(fd, view)
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)


def fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def ensure_real_dirs(root: Path, rel_parts: tuple[str, ...]) -> Path:
    """Create ``root/part1/part2...`` refusing any symlink or non-directory on the way.

    ``root`` must already be resolved. Each component is created with
    ``os.mkdir`` (never makedirs) and checked with ``lstat`` afterwards so a
    symlink planted between creation steps is detected.
    """
    current = root
    for part in rel_parts:
        current = current / part
        try:
            os.mkdir(current)
        except FileExistsError:
            pass
        st = os.lstat(current)
        if stat.S_ISLNK(st.st_mode):
            raise UnsafePathError(f"refusing symlinked directory: {current}")
        if not stat.S_ISDIR(st.st_mode):
            raise UnsafePathError(f"not a directory: {current}")
    if os.path.realpath(current) != str(current):
        raise UnsafePathError(f"directory resolves outside its expected location: {current}")
    return current


def check_no_symlinks(root: Path, rel_parts: tuple[str, ...]) -> list[str]:
    """Read-only variant of ensure_real_dirs: report problems without creating anything."""
    problems = []
    current = root
    for part in rel_parts:
        current = current / part
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            break
        if stat.S_ISLNK(st.st_mode):
            problems.append(f"symlinked path: {current}")
            break
        if not stat.S_ISDIR(st.st_mode):
            problems.append(f"not a directory: {current}")
            break
    return problems


# --- no-replace rename -----------------------------------------------------

class NoReplaceUnsupported(OSError):
    pass


_libc = None


def _get_libc():
    global _libc
    if _libc is None:
        name = ctypes.util.find_library("c")
        _libc = ctypes.CDLL(name, use_errno=True) if name else False
    return _libc or None


def rename_noreplace(src: Path, dst: Path) -> None:
    """Atomically rename ``src`` to ``dst`` failing with FileExistsError if ``dst`` exists.

    Uses renamex_np(RENAME_EXCL) on macOS and renameat2(RENAME_NOREPLACE) on
    Linux. Raises NoReplaceUnsupported where neither is available so callers
    can fall back to a reservation protocol or fail safely.
    """
    libc = _get_libc()
    s, d = os.fsencode(src), os.fsencode(dst)
    if libc is not None and sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        RENAME_EXCL = 0x00000004
        if libc.renamex_np(s, d, RENAME_EXCL) == 0:
            return
        _raise_rename_error(ctypes.get_errno(), src, dst)
    if libc is not None and sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        AT_FDCWD, RENAME_NOREPLACE = -100, 1
        if libc.renameat2(AT_FDCWD, s, AT_FDCWD, d, RENAME_NOREPLACE) == 0:
            return
        _raise_rename_error(ctypes.get_errno(), src, dst)
    raise NoReplaceUnsupported(errno.ENOSYS, "no-replace rename is not available on this platform")


def _raise_rename_error(err: int, src: Path, dst: Path) -> None:
    if err in (errno.EEXIST, errno.ENOTEMPTY):
        raise FileExistsError(err, os.strerror(err), str(dst))
    if err in (errno.ENOSYS, errno.EINVAL, errno.ENOTSUP, getattr(errno, "EOPNOTSUPP", errno.ENOTSUP)):
        raise NoReplaceUnsupported(err, os.strerror(err), str(dst))
    raise OSError(err, os.strerror(err), str(src))


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True
