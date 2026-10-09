"""Discover canonical skills and parse their frontmatter."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from engkit import fsutil

# \Z, not $: "$" would accept a trailing newline.
NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
NAME_MAX = 64
DESCRIPTION_MAX = 1024


@dataclass
class Skill:
    name: str
    path: Path
    description: str
    metadata: dict
    body: str

    @property
    def skill_md(self) -> Path:
        return self.path / "SKILL.md"


@dataclass
class Issue:
    path: Path
    message: str
    level: str = "error"  # error | warning

    def format(self) -> str:
        return fsutil.printable(f"{self.level}: {self.path}: {self.message}")


@dataclass
class CatalogResult:
    skills: list[Skill] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.level == "error" for i in self.issues)


class FrontmatterError(ValueError):
    pass


MAX_FRONTMATTER_BYTES = 64 * 1024


def _parse_frontmatter_yaml(raw: str):
    if len(raw.encode("utf-8")) > MAX_FRONTMATTER_BYTES:
        raise FrontmatterError("frontmatter is larger than 64 KiB")
    try:
        return yaml.safe_load(raw)
    except RecursionError:
        raise FrontmatterError("frontmatter is too deeply nested") from None
    except ValueError as exc:  # e.g. an impossible calendar date such as 2026-13-45
        raise FrontmatterError(f"invalid frontmatter value: {exc}") from None
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" at frontmatter line {mark.line + 1}" if mark else ""
        problem = getattr(exc, "problem", exc)
        raise FrontmatterError(f"malformed YAML{where}: {problem}") from None


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (metadata, body); frontmatter is the first block delimited by '---' lines."""
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise FrontmatterError("missing YAML frontmatter (file must start with '---')")
    for index in range(1, len(lines)):
        if lines[index].rstrip("\r\n") == "---":
            raw = "".join(lines[1:index])
            body = "".join(lines[index + 1 :])
            break
    else:
        raise FrontmatterError("unterminated YAML frontmatter (no closing '---')")
    data = _parse_frontmatter_yaml(raw)
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping")
    return data, body


def _load_skill(entry: Path, issues: list[Issue]) -> Skill | None:
    skill_md = entry / "SKILL.md"
    if skill_md.is_symlink():
        issues.append(Issue(skill_md, "SKILL.md must be a regular file, not a symlink"))
        return None
    if not skill_md.is_file():
        issues.append(Issue(skill_md, "missing SKILL.md"))
        return None
    if skill_md.stat().st_size > fsutil.MAX_SKILL_FILE_BYTES:
        issues.append(Issue(skill_md, "SKILL.md is larger than 1 MiB"))
        return None
    try:
        metadata, body = split_frontmatter(skill_md.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        issues.append(Issue(skill_md, "SKILL.md is not valid UTF-8"))
        return None
    except FrontmatterError as exc:
        issues.append(Issue(skill_md, str(exc)))
        return None
    name = metadata.get("name")
    description = metadata.get("description")
    return Skill(
        name=name if isinstance(name, str) else "",
        path=entry,
        description=description.strip() if isinstance(description, str) else "",
        metadata=metadata,
        body=body,
    )


def _reject_duplicates(result: CatalogResult) -> None:
    groups: dict[str, list[Skill]] = {}
    for skill in result.skills:
        if skill.name:
            groups.setdefault(skill.name, []).append(skill)
    duplicates = {name for name, group in groups.items() if len(group) > 1}
    for name in sorted(duplicates):
        paths = ", ".join(str(skill.path) for skill in groups[name])
        for skill in groups[name]:
            message = f"duplicate skill name '{name}' (also in: {paths})"
            result.issues.append(Issue(skill.path / "SKILL.md", message))
    result.skills = [skill for skill in result.skills if skill.name not in duplicates]


def builtin_skills_dir() -> Path:
    """The skills directory packaged with engkit; never depends on the working directory."""
    return Path(__file__).resolve().parent / "skills"


def discover(base: Path) -> CatalogResult:
    """Enumerate ``base/*/SKILL.md``; skills with a duplicate name are all excluded."""
    result = CatalogResult()
    if not base.is_dir():
        result.issues.append(Issue(base, "skills directory not found"))
        return result
    for entry in sorted(base.iterdir(), key=lambda path: path.name):
        if entry.name.startswith("."):
            continue
        if entry.is_symlink():
            result.issues.append(Issue(entry, "skill directory must not be a symlink"))
            continue
        if not entry.is_dir():
            continue
        skill = _load_skill(entry, result.issues)
        if skill is not None:
            result.skills.append(skill)
    _reject_duplicates(result)
    return result
