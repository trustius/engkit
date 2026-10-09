"""Project memory: a small local store of facts that cannot be derived from code or git."""

from __future__ import annotations

import datetime
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path

from engkit import fsutil
from engkit.catalog import FrontmatterError, Issue, split_frontmatter

MEMORY_REL = ".engkit/memory"
CLAUDE_SNIPPET = "@.engkit/memory/INDEX.md\n"
AGENTS_SNIPPET = (
    "Read .engkit/memory/INDEX.md at task start and open only the entries relevant to the task.\n"
)
INDEX_HEADER = "# Project memory\n\n"
MAX_INDEX_LINES = 150
MAX_ENTRY_LINES = 60
TYPES = ("context", "decision", "convention", "gotcha", "task-state")
STATUSES = ("verified", "hypothesis", "assumption")
NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
INDEX_LINE = re.compile(r"- \[(.+)\]\(([^()]+\.md)\) — ([a-z-]+) — (.+)")
PLACEHOLDER = re.compile(
    r"(?i)<.*>|\$\{?\w+.*|.*(example|changeme|placeholder|redacted|xxx|\*\*\*).*"
)
SECRET_PATTERNS = (
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("API secret key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("Slack token", re.compile(r"xox[abp]-[A-Za-z0-9-]{10,}")),
)
ASSIGNMENT = re.compile(
    r"(?i)\b\w*(?:key|password|passwd|secret|token)\w*\s*[:=]\s*[\"']?([^\s\"',]+)"
)


@dataclass
class InitResult:
    created: list[str] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)


def init(project_root: Path) -> InitResult:
    result = InitResult()
    memory_dir = fsutil.ensure_real_dirs(project_root, (".engkit", "memory"))
    files = ((".gitignore", b"*\n"), ("INDEX.md", INDEX_HEADER.encode()))
    for name, content in files:
        rel = f"{MEMORY_REL}/{name}"
        try:
            fsutil.write_file(memory_dir / name, content, exclusive=True)
        except FileExistsError:
            result.existing.append(rel)
            continue
        result.created.append(rel)
    return result


def _memory_dir_issues(project_root: Path) -> tuple[Path | None, list[Issue]]:
    memory_dir = project_root / MEMORY_REL
    for directory in (project_root / ".engkit", memory_dir):
        if directory.is_symlink():
            return None, [Issue(directory, "must not be a symlink")]
    if not memory_dir.is_dir():
        message = "no project memory; run `engkit memory init`"
        return None, [Issue(memory_dir, message)]
    return memory_dir, []


def _entry_paths(memory_dir: Path) -> list[Path]:
    paths = sorted(memory_dir.glob("*.md"))
    return [path for path in paths if path.name != "INDEX.md" and not path.name.startswith(".")]


def _check_date(value: object) -> bool:
    if isinstance(value, datetime.date):
        return True
    if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _check_metadata(path: Path, meta: dict) -> list[Issue]:
    problems = []
    name = meta.get("name")
    if not isinstance(name, str) or len(name) > 64 or not NAME_PATTERN.fullmatch(name):
        problems.append("name must be lower-case letters, digits, single hyphens, at most 64")
    elif name != path.stem:
        problems.append(f"name {name!r} must equal the file stem {path.stem!r}")
    if meta.get("type") not in TYPES:
        problems.append(f"type must be one of {', '.join(TYPES)}")
    if meta.get("status") not in STATUSES:
        problems.append(f"status must be one of {', '.join(STATUSES)}")
    if not _check_date(meta.get("updated")):
        problems.append("updated must be an absolute ISO date (YYYY-MM-DD)")
    sources = meta.get("sources")
    if not isinstance(sources, list) or not all(isinstance(item, str) for item in sources):
        problems.append("sources must be a list of strings")
    return [Issue(path, message) for message in problems]


def _secret_issues(path: Path, text: str) -> list[Issue]:
    issues = []
    for number, line in enumerate(text.splitlines(), start=1):
        kinds = [label for label, pattern in SECRET_PATTERNS if pattern.search(line)]
        match = ASSIGNMENT.search(line)
        if match and not PLACEHOLDER.fullmatch(match.group(1)):
            kinds.append("credential assignment")
        for kind in kinds:
            message = f"line {number}: possible secret ({kind}); value not shown"
            issues.append(Issue(path, message, "warning"))
    return issues


def _read_entry(path: Path) -> tuple[dict | None, list[Issue]]:
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        return None, [Issue(path, "entry must be a regular file, not a symlink")]
    text = path.read_text(encoding="utf-8", errors="replace")
    issues = _secret_issues(path, text)
    if len(text.splitlines()) > MAX_ENTRY_LINES:
        issues.append(Issue(path, f"entry exceeds {MAX_ENTRY_LINES} lines"))
    try:
        meta, _ = split_frontmatter(text)
    except FrontmatterError as exc:
        return None, issues + [Issue(path, str(exc))]
    issues.extend(_check_metadata(path, meta))
    return meta, issues


def _index_issues(memory_dir: Path, entries: dict[str, dict | None]) -> list[Issue]:
    index_path = memory_dir / "INDEX.md"
    if not index_path.is_file() or index_path.is_symlink():
        return [Issue(index_path, "INDEX.md must exist as a regular file")]
    lines = index_path.read_text(encoding="utf-8", errors="replace").splitlines()
    issues = []
    if len(lines) > MAX_INDEX_LINES:
        issues.append(Issue(index_path, f"INDEX.md exceeds {MAX_INDEX_LINES} lines"))
    listed: list[str] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip() or line.startswith("#"):
            continue
        match = INDEX_LINE.fullmatch(line)
        if not match:
            message = f"line {number}: does not match '- [Title](slug.md) — type — summary'"
            issues.append(Issue(index_path, message, "warning"))
            continue
        issues.extend(_link_issues(index_path, number, match, entries))
        listed.append(match.group(2))
    for name in entries:
        if listed.count(name) == 0:
            issues.append(Issue(memory_dir / name, "entry is not listed in INDEX.md"))
        if listed.count(name) > 1:
            issues.append(Issue(memory_dir / name, "entry is listed more than once in INDEX.md"))
    return issues


def _link_issues(index_path: Path, number: int, match: re.Match, entries: dict) -> list[Issue]:
    target, listed_type = match.group(2), match.group(3)
    if target not in entries:
        return [Issue(index_path, f"line {number}: link target {target} does not exist")]
    meta = entries[target]
    if meta is not None and meta.get("type") != listed_type:
        message = (
            f"line {number}: type {listed_type!r} differs from entry type {meta.get('type')!r}"
        )
        return [Issue(index_path, message)]
    return []


def validate(project_root: Path) -> list[Issue]:
    memory_dir, issues = _memory_dir_issues(project_root)
    if memory_dir is None:
        return issues
    entries: dict[str, dict | None] = {}
    for path in _entry_paths(memory_dir):
        meta, entry_issues = _read_entry(path)
        entries[path.name] = meta
        issues.extend(entry_issues)
    issues.extend(_index_issues(memory_dir, entries))
    return issues


def status(project_root: Path) -> tuple[str, str]:
    memory_dir = project_root / MEMORY_REL
    if not memory_dir.exists() and not memory_dir.is_symlink():
        return "info", "no project memory (optional; `engkit memory init` creates it)"
    issues = validate(project_root)
    errors = len([issue for issue in issues if issue.level == "error"])
    warnings = len(issues) - errors
    if errors == 0 and warnings == 0:
        count = len(_entry_paths(memory_dir))
        return "info", f"project memory: {count} entries ok"
    level = "error" if errors else "warning"
    return level, f"project memory: {errors} errors, {warnings} warnings"
