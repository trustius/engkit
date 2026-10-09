"""Read-only validation of canonical skills; never executes files."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

from engkit import fsutil
from engkit.catalog import (
    DESCRIPTION_MAX,
    NAME_MAX,
    NAME_RE,
    CatalogResult,
    Issue,
    Skill,
    discover,
)
from engkit.platforms import builtin_collisions

REQUIRED_SECTIONS = (
    "When to use",
    "When to ask",
    "Objective",
    "Inputs",
    "Workflow",
    "Output contract",
    "Guardrails",
)
# Verbatim lines every skill repeats under "## Guardrails" (installed skills must be
# self-contained, so they cannot import a shared file). Quoted in docs/skill-authoring.md.
SHARED_GUARDRAILS = (
    "- Plans: write any plan (two or more steps of future work) to"
    " `docs/plans/YYYY-MM-DD-<slug>.md` at the project root; if that name exists, use"
    " `<slug>-2.md`, then `<slug>-3.md`; never overwrite a file; report the path. If today's"
    " date is unknown, ask.",
    "- No auto-run on servers: never run anything automatically on a server environment (prod,"
    " staging, dev, test), including its databases, clusters, queues and cloud accounts. Never run"
    " a state-changing action there; write the exact steps for the user. A read-only command"
    " (status, logs) runs only after the user says yes to that exact command. If unsure whether a"
    " target is a server environment, treat it as one and ask.",
    "- Sensitive data: never print, copy or store keys, tokens, passwords, connection strings, PII"
    " or PHI, whether in chat, plans, memory or files. Refer to them by location (`file:line`) and"
    " write `[REDACTED]`. Use synthetic data in examples.",
    "- Incremental: work in small steps; after each step, check the result and report it; stop at"
    " the first failed check and ask.",
)
PORTABLE_KEYS = {"name", "description", "license", "metadata", "allowed-tools", "compatibility"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
URL_SCHEME_RE = re.compile(r"[a-z][a-z0-9+.-]*:")
CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
SKILL_MD_MAX_LINES = 120


def validate_name(name: object) -> str | None:
    if not isinstance(name, str) or not name:
        return "name must be a non-empty string"
    if len(name) > NAME_MAX:
        return f"name exceeds {NAME_MAX} characters"
    if not NAME_RE.fullmatch(name):
        return (
            "name must use lower-case ASCII letters, digits and single hyphens "
            "(no leading/trailing hyphen)"
        )
    return None


def _check_names(skill: Skill) -> list[Issue]:
    issues: list[Issue] = []
    name = skill.metadata.get("name")
    message = validate_name(name)
    if message:
        issues.append(Issue(skill.skill_md, message))
    elif name != skill.path.name:
        issues.append(
            Issue(skill.skill_md, f"name '{name}' does not match directory '{skill.path.name}'")
        )
    directory_message = validate_name(skill.path.name)
    if directory_message:
        issues.append(Issue(skill.path, f"directory name invalid: {directory_message}"))
    collisions = builtin_collisions(skill.path.name)
    if collisions:
        platforms = ", ".join(collisions)
        message = f"name collides with a built-in skill of: {platforms}; choose another name"
        issues.append(Issue(skill.skill_md, message))
    return issues


def _check_metadata(skill: Skill) -> list[Issue]:
    issues: list[Issue] = []
    description = skill.metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        issues.append(Issue(skill.skill_md, "description must be a non-empty string"))
    elif len(description) > DESCRIPTION_MAX:
        issues.append(Issue(skill.skill_md, f"description exceeds {DESCRIPTION_MAX} characters"))
    for key in sorted(set(skill.metadata) - PORTABLE_KEYS):
        issues.append(Issue(skill.skill_md, f"non-portable frontmatter key '{key}'", "warning"))
    return issues


def _check_sections(skill: Skill) -> list[Issue]:
    headings = HEADING_RE.findall(skill.body)
    missing = [section for section in REQUIRED_SECTIONS if section not in headings]
    if missing:
        listed = ", ".join(f"'## {section}'" for section in missing)
        return [Issue(skill.skill_md, f"missing required sections: {listed}")]
    positions = [headings.index(section) for section in REQUIRED_SECTIONS]
    if positions != sorted(positions):
        return [Issue(skill.skill_md, "required sections are out of order", "warning")]
    return []


def _check_length(skill: Skill) -> list[Issue]:
    line_count = len(skill.skill_md.read_text(encoding="utf-8").splitlines())
    if line_count <= SKILL_MD_MAX_LINES:
        return []
    message = (
        f"SKILL.md has {line_count} lines (max {SKILL_MD_MAX_LINES}); move detail to references/"
    )
    return [Issue(skill.skill_md, message)]


def validate_skill(
    skill: Skill, containment_root: Path, *, require_shared_guardrails: bool = False
) -> list[Issue]:
    issues = _check_names(skill)
    issues.extend(_check_metadata(skill))
    issues.extend(_check_sections(skill))
    issues.extend(_check_length(skill))
    if require_shared_guardrails:
        issues.extend(_check_shared_guardrails(skill))
    issues.extend(_check_links(skill))
    issues.extend(_check_tree(skill.path, containment_root))
    return issues


GUARDRAILS_RE = re.compile(r"^## Guardrails\s*$", re.MULTILINE)


def _guardrail_lines(body: str) -> list[str]:
    match = GUARDRAILS_RE.search(body)
    if match is None:
        return []
    return re.split(r"^## ", body[match.end() :], maxsplit=1, flags=re.MULTILINE)[0].splitlines()


def _shared_guardrail_issues(lines: list[str], skill_md: Path) -> list[Issue]:
    issues = []
    for shared in SHARED_GUARDRAILS:
        if shared in lines:
            continue
        label = shared.split(":", 1)[0] + ":"
        state = "altered" if any(line.startswith(label) for line in lines) else "missing"
        message = f"{state} shared guardrail '{label[2:]}' under '## Guardrails' (copy it verbatim)"
        issues.append(Issue(skill_md, message))
    return issues


def _check_shared_guardrails(skill: Skill) -> list[Issue]:
    skill_md = skill.path / "SKILL.md"
    if len(GUARDRAILS_RE.findall(skill.body)) > 1:
        return [Issue(skill_md, "'## Guardrails' appears more than once")]
    lines = _guardrail_lines(skill.body)
    issues = _shared_guardrail_issues(lines, skill_md)
    first = [line for line in lines if line.strip()][: len(SHARED_GUARDRAILS)]
    if not issues and first != list(SHARED_GUARDRAILS):
        message = "shared guardrails must be the first lines under '## Guardrails', in order"
        issues.append(Issue(skill_md, message))
    return issues


def _check_links(skill: Skill) -> list[Issue]:
    issues = []
    skill_root = skill.path.resolve()
    # Links inside code are examples, not references.
    for target in LINK_RE.findall(CODE_RE.sub("", skill.body)):
        if URL_SCHEME_RE.match(target) or target.startswith("#"):
            continue  # URL or in-page anchor
        target = target.split("#", 1)[0]
        if not target:
            continue
        if target.startswith("/"):
            issues.append(Issue(skill.skill_md, f"reference '{target}' must be relative"))
            continue
        resolved = (skill.path / target).resolve()
        if not resolved.is_relative_to(skill_root):
            issues.append(
                Issue(skill.skill_md, f"reference '{target}' escapes the skill directory")
            )
        elif not resolved.exists():
            issues.append(Issue(skill.skill_md, f"missing reference '{target}'"))
    return issues


def _check_entry(path: Path, containment_root: Path, skill_root: Path) -> list[Issue]:
    issues = []
    if fsutil.printable(path.name) != path.name:
        issues.append(Issue(path, "file or directory name contains control characters"))
    if not path.is_symlink():
        if not (path.is_dir() or path.is_file()):
            issues.append(Issue(path, "special files are not allowed in skills"))
        return issues
    target = Path(os.path.realpath(path))
    link = os.readlink(path)
    if not target.is_relative_to(containment_root):
        issues.append(Issue(path, f"symlink escapes the skills directory (-> {link})"))
    elif not target.is_relative_to(skill_root):
        issues.append(Issue(path, f"symlink escapes the skill directory (-> {link})"))
    else:
        # The installer refuses any symlink, so validation must fail too.
        issues.append(Issue(path, "symlinks cannot be installed; replace with a regular file"))
    return issues


def _check_sizes(skill_dir: Path, sizes: list[int]) -> list[Issue]:
    sizes = [size for size in sizes if size >= 0]
    issues = []
    if len(sizes) > fsutil.MAX_SKILL_FILES:
        issues.append(Issue(skill_dir, f"skill has more than {fsutil.MAX_SKILL_FILES} files"))
    if any(size > fsutil.MAX_SKILL_FILE_BYTES for size in sizes):
        issues.append(Issue(skill_dir, "skill has a file larger than 1 MiB"))
    if sum(sizes) > fsutil.MAX_SKILL_BYTES:
        issues.append(Issue(skill_dir, "skill is larger than 10 MiB in total"))
    return issues


def _regular_size(path: Path) -> int:
    """Size of a regular file; -1 for anything else."""
    info = os.lstat(path)
    if stat.S_ISREG(info.st_mode):
        return info.st_size
    return -1


def _check_tree(skill_dir: Path, containment_root: Path) -> list[Issue]:
    issues = []
    sizes = []
    root = containment_root.resolve()
    skill_root = skill_dir.resolve()
    try:
        for _, path in fsutil.entries(skill_dir):
            issues.extend(_check_entry(path, root, skill_root))
            sizes.append(_regular_size(path))
    except OSError as exc:
        issues.append(Issue(skill_dir, f"cannot read skill directory: {exc}"))
    return issues + _check_sizes(skill_dir, sizes)


def validate(skills_dir: Path, name: str | None = None) -> CatalogResult:
    """Validate all skills (or one); symlinks may not leave ``skills_dir``."""
    return validate_dir(skills_dir, skills_dir, name, require_shared_guardrails=True)


def validate_dir(
    skills_dir: Path,
    containment_root: Path,
    name: str | None = None,
    *,
    require_shared_guardrails: bool = False,
) -> CatalogResult:
    """Validate skills under ``skills_dir``; symlinks must stay inside ``containment_root``."""
    catalog = discover(skills_dir)
    if name is None:
        selected = catalog.skills
        catalog_issues = list(catalog.issues)
    else:
        message = validate_name(name)
        if message:
            return CatalogResult(issues=[Issue(Path(name), f"invalid skill name: {message}")])
        selected = [skill for skill in catalog.skills if skill.path.name == name]
        skill_path = skills_dir / name
        catalog_issues = [i for i in catalog.issues if i.path.is_relative_to(skill_path)]
        if not selected and not catalog_issues:
            catalog_issues.append(Issue(skill_path, "unknown skill"))
    result = CatalogResult(skills=selected, issues=catalog_issues)
    for skill in selected:
        issues = validate_skill(
            skill, containment_root, require_shared_guardrails=require_shared_guardrails
        )
        result.issues.extend(issues)
    return result
