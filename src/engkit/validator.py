"""Validate canonical skills. Read-only: no network, no writes, never executes files."""

from __future__ import annotations

import os
import re
from pathlib import Path

from engkit.catalog import (
    DESCRIPTION_MAX,
    NAME_MAX,
    NAME_RE,
    CatalogResult,
    Issue,
    Skill,
    discover,
)
from engkit.fsutil import is_within

REQUIRED_SECTIONS = (
    "When to use",
    "Objective",
    "Inputs",
    "Project context (optional)",
    "Workflow",
    "Output contract",
    "Guardrails",
)
PORTABLE_KEYS = {"name", "description", "license", "metadata", "allowed-tools", "compatibility"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
SKILL_MD_SOFT_LIMIT = 500


def validate_name(name: object) -> str | None:
    if not isinstance(name, str) or not name:
        return "name must be a non-empty string"
    if len(name) > NAME_MAX:
        return f"name exceeds {NAME_MAX} characters"
    if not NAME_RE.match(name):
        return "name must use lower-case ASCII letters, digits and single hyphens (no leading/trailing hyphen)"
    return None


def validate_skill(skill: Skill, toolkit_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    skill_md = skill.path / "SKILL.md"
    meta = skill.metadata

    err = validate_name(meta.get("name"))
    if err:
        issues.append(Issue(skill_md, err))
    elif meta["name"] != skill.path.name:
        issues.append(Issue(skill_md, f"name '{meta['name']}' does not match directory '{skill.path.name}'"))
    dir_err = validate_name(skill.path.name)
    if dir_err:
        issues.append(Issue(skill.path, f"directory name invalid: {dir_err}"))

    desc = meta.get("description")
    if not isinstance(desc, str) or not desc.strip():
        issues.append(Issue(skill_md, "description must be a non-empty string"))
    elif len(desc) > DESCRIPTION_MAX:
        issues.append(Issue(skill_md, f"description exceeds {DESCRIPTION_MAX} characters"))

    for key in sorted(set(meta) - PORTABLE_KEYS):
        issues.append(Issue(skill_md, f"non-portable frontmatter key '{key}'", "warning"))

    headings = HEADING_RE.findall(skill.body)
    missing = [s for s in REQUIRED_SECTIONS if s not in headings]
    if missing:
        issues.append(Issue(skill_md, "missing required sections: " + ", ".join(f"'## {m}'" for m in missing)))
    else:
        order = [headings.index(s) for s in REQUIRED_SECTIONS]
        if order != sorted(order):
            issues.append(Issue(skill_md, "required sections are out of order", "warning"))

    if skill.body.count("\n") > SKILL_MD_SOFT_LIMIT:
        issues.append(Issue(skill_md, f"body exceeds {SKILL_MD_SOFT_LIMIT} lines; move detail to references/", "warning"))

    issues.extend(_check_links(skill, skill_md))
    issues.extend(_check_tree(skill.path, toolkit_root))
    return issues


def _check_links(skill: Skill, skill_md: Path) -> list[Issue]:
    issues = []
    skill_root = skill.path.resolve()
    for target in LINK_RE.findall(skill.body):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue  # URL or in-page anchor
        target = target.split("#", 1)[0]
        if not target:
            continue
        if target.startswith("/"):
            issues.append(Issue(skill_md, f"reference '{target}' must be relative"))
            continue
        resolved = (skill.path / target).resolve()
        if not is_within(resolved, skill_root):
            issues.append(Issue(skill_md, f"reference '{target}' escapes the skill directory"))
        elif not resolved.exists():
            issues.append(Issue(skill_md, f"missing reference '{target}'"))
    return issues


def _check_tree(skill_dir: Path, toolkit_root: Path) -> list[Issue]:
    issues = []
    root = toolkit_root.resolve()
    skill_root = skill_dir.resolve()
    for dirpath, dirnames, filenames in os.walk(skill_dir, followlinks=False):
        for name in dirnames + filenames:
            p = Path(dirpath) / name
            if not p.is_symlink():
                if not (p.is_dir() or p.is_file()):
                    issues.append(Issue(p, "special files are not allowed in skills"))
                continue
            target = Path(os.path.realpath(p))
            if not is_within(target, root):
                issues.append(Issue(p, f"symlink escapes toolkit root (-> {os.readlink(p)})"))
            elif not is_within(target, skill_root):
                issues.append(Issue(p, f"symlink escapes the skill directory (-> {os.readlink(p)})"))
            else:
                # The installer refuses any symlink, so validation must fail too.
                issues.append(Issue(p, "symlinks cannot be installed; replace with a regular file"))
    return issues


def validate(toolkit_root: Path, name: str | None = None) -> CatalogResult:
    """Validate all skills (or one). Returns a CatalogResult whose issues include catalog problems."""
    catalog = discover(toolkit_root)
    if name is not None:
        err = validate_name(name)
        if err:
            return CatalogResult(issues=[Issue(Path(name), f"invalid skill name: {err}")])
        selected = [s for s in catalog.skills if s.path.name == name]
        catalog_issues = [i for i in catalog.issues if _issue_in(i, toolkit_root / "skills" / name)]
        if not selected and not catalog_issues:
            catalog_issues.append(Issue(toolkit_root / "skills" / name, "unknown skill"))
    else:
        selected = catalog.skills
        catalog_issues = list(catalog.issues)
    out = CatalogResult(skills=selected, issues=catalog_issues)
    for skill in selected:
        out.issues.extend(validate_skill(skill, toolkit_root))
    return out


def _issue_in(issue: Issue, path: Path) -> bool:
    return issue.path == path or is_within(issue.path, path)
