"""Discover canonical skills and parse their frontmatter."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_MAX = 64
DESCRIPTION_MAX = 1024


@dataclass
class Skill:
    name: str
    path: Path
    description: str
    metadata: dict
    body: str


@dataclass
class Issue:
    path: Path
    message: str
    level: str = "error"  # error | warning

    def format(self) -> str:
        return f"{self.level}: {self.path}: {self.message}"


@dataclass
class CatalogResult:
    skills: list[Skill] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.level == "error" for i in self.issues)


class FrontmatterError(ValueError):
    pass


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (metadata, body). Frontmatter must be the first block delimited by '---' lines."""
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise FrontmatterError("missing YAML frontmatter (file must start with '---')")
    for idx in range(1, len(lines)):
        if lines[idx].rstrip("\r\n") == "---":
            raw = "".join(lines[1:idx])
            body = "".join(lines[idx + 1 :])
            break
    else:
        raise FrontmatterError("unterminated YAML frontmatter (no closing '---')")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" at frontmatter line {mark.line + 1}" if mark else ""
        raise FrontmatterError(f"malformed YAML{where}: {getattr(exc, 'problem', exc)}") from None
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping")
    return data, body


def skills_dir(root: Path) -> Path:
    return root / "skills"


def discover(root: Path) -> CatalogResult:
    """Deterministically enumerate ``root/skills/*/SKILL.md``.

    Hidden entries are ignored. Problems are reported as issues; skills with
    unreadable metadata are excluded from ``skills``. Duplicate frontmatter
    names are errors and every duplicate is excluded.
    """
    result = CatalogResult()
    base = skills_dir(root)
    if not base.is_dir():
        result.issues.append(Issue(base, "skills directory not found"))
        return result
    for entry in sorted(base.iterdir(), key=lambda p: p.name):
        if entry.name.startswith("."):
            continue
        if entry.is_symlink():
            result.issues.append(Issue(entry, "skill directory must not be a symlink"))
            continue
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if skill_md.is_symlink() or not skill_md.is_file():
            reason = "SKILL.md must be a regular file, not a symlink" if skill_md.is_symlink() else "missing SKILL.md"
            result.issues.append(Issue(skill_md, reason))
            continue
        try:
            meta, body = split_frontmatter(skill_md.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            result.issues.append(Issue(skill_md, "SKILL.md is not valid UTF-8"))
            continue
        except FrontmatterError as exc:
            result.issues.append(Issue(skill_md, str(exc)))
            continue
        name = meta.get("name")
        desc = meta.get("description")
        result.skills.append(
            Skill(
                name=name if isinstance(name, str) else "",
                path=entry,
                description=desc.strip() if isinstance(desc, str) else "",
                metadata=meta,
                body=body,
            )
        )
    seen: dict[str, list[Skill]] = {}
    for s in result.skills:
        if s.name:
            seen.setdefault(s.name, []).append(s)
    dupes = {n for n, group in seen.items() if len(group) > 1}
    for n in sorted(dupes):
        paths = ", ".join(str(s.path) for s in seen[n])
        for s in seen[n]:
            result.issues.append(Issue(s.path / "SKILL.md", f"duplicate skill name '{n}' (also in: {paths})"))
    result.skills = [s for s in result.skills if s.name not in dupes]
    return result


def find(root: Path, name: str) -> tuple[Skill | None, CatalogResult]:
    result = discover(root)
    for s in result.skills:
        if s.name == name and s.path.name == name:
            return s, result
    return None, result
