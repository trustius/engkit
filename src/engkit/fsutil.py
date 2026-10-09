"""Standard-library filesystem helpers; nothing here executes files."""

from __future__ import annotations

import contextlib
import ctypes
import ctypes.util
import errno
import hashlib
import os
import shutil
import stat
import sys
import uuid
from pathlib import Path

MAX_SKILL_FILES = 500
MAX_SKILL_FILE_BYTES = 1024 * 1024
MAX_SKILL_BYTES = 10 * 1024 * 1024


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


def printable(text: str) -> str:
    """Escape non-printable characters so fetched text cannot drive the terminal."""
    return "".join(_escape(char) for char in text)


def _escape(char: str) -> str:
    if char.isprintable():
        return char
    code = ord(char)
    if code <= 0xFF:
        return f"\\x{code:02x}"
    if code <= 0xFFFF:
        return f"\\u{code:04x}"
    return f"\\U{code:08x}"


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


def _raise(exc: OSError) -> None:
    raise exc


def entries(root: Path):
    """Yield (relative POSIX key, path) of every entry below ``root``, never following symlinks."""
    # os.walk ignores errors by default, which would hide unreadable directories.
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False, onerror=_raise):
        base = Path(dirpath)
        prefix = base.relative_to(root).as_posix()
        for name in sorted(dirnames + filenames):
            yield name if prefix == "." else f"{prefix}/{name}", base / name


def _file_digest(path: Path) -> str:
    """Return sha256 of a regular file, "" for a directory; refuse everything else.

    Only the executable bit is part of the digest; other mode bits vary with the umask.
    """
    mode = os.lstat(path).st_mode
    if stat.S_ISREG(mode):
        marker = "+x" if mode & 0o111 else ""
        return sha256_file(path) + marker
    if stat.S_ISDIR(mode):
        return ""
    raise UnsafePathError(f"refusing symlink or special file: {path}")


def tree_snapshot(root: Path) -> dict[str, str]:
    """Map relative POSIX path to sha256 (plus "+x" if executable) of every regular file.

    Empty directories are recorded as "<dir>"; symlinks and special files raise UnsafePathError.
    """
    result: dict[str, str] = {}
    directories = []
    for key, path in entries(root):
        digest = _file_digest(path)
        if digest:
            result[key] = digest
        else:
            directories.append(key)
    parents = {key.rpartition("/")[0] for key in [*result, *directories]}
    result.update({key: "<dir>" for key in directories if key not in parents})
    return result


def copy_tree_regular(source: Path, destination: Path) -> None:
    """Copy regular files and directories only; ``destination`` must not exist."""
    os.mkdir(destination)
    for key, path in entries(source):
        if path.is_symlink():
            raise UnsafePathError(f"refusing symlink: {path}")
        if path.is_dir():
            os.mkdir(destination / key)
        else:
            _copy_file(path, destination / key)


def _copy_file(source: Path, destination: Path) -> None:
    mode = os.lstat(source).st_mode
    if not stat.S_ISREG(mode):
        raise UnsafePathError(f"refusing non-regular file: {source}")
    read_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    write_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    reader = os.fdopen(os.open(source, read_flags), "rb")
    writer = os.fdopen(os.open(destination, write_flags, mode & 0o777), "wb")
    with reader, writer:
        shutil.copyfileobj(reader, writer)
        writer.flush()
        os.fsync(writer.fileno())


def write_file(path: Path, data: bytes, *, exclusive: bool = True, mode: int = 0o644) -> None:
    """Write bytes and fsync; ``exclusive`` refuses to replace an existing path."""
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    with os.fdopen(os.open(path, flags | getattr(os, "O_NOFOLLOW", 0), mode), "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def replace_file(path: Path, data: bytes) -> None:
    """Atomically replace ``path`` through a temporary sibling."""
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        write_file(temporary, data)
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise
    fsync_dir(path.parent)


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


def _dir_problem(path: Path) -> str:
    """Describe why ``path`` is not a real directory; empty when it is."""
    mode = os.lstat(path).st_mode
    if stat.S_ISLNK(mode):
        return f"symlinked directory: {path}"
    if not stat.S_ISDIR(mode):
        return f"not a directory: {path}"
    return ""


def ensure_real_dirs(root: Path, rel_parts: tuple[str, ...]) -> Path:
    """Create ``root/parts...`` refusing symlinks; ``root`` must already be resolved."""
    # mkdir then lstat per part (not makedirs) so a symlink planted between steps is caught.
    current = root
    for part in rel_parts:
        current = current / part
        with contextlib.suppress(FileExistsError):
            os.mkdir(current)
        problem = _dir_problem(current)
        if problem:
            raise UnsafePathError(f"refusing {problem}")
    if os.path.realpath(current) != str(current):
        raise UnsafePathError(f"directory resolves outside its expected location: {current}")
    return current


def check_no_symlinks(root: Path, rel_parts: tuple[str, ...]) -> list[str]:
    """Read-only variant of ensure_real_dirs: report problems without creating anything."""
    current = root
    for part in rel_parts:
        current = current / part
        try:
            problem = _dir_problem(current)
        except FileNotFoundError:
            return []
        if problem:
            return [problem]
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
