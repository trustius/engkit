"""Read-only diagnostics. Never repairs, installs or deletes anything."""

from __future__ import annotations

import os
import platform as python_platform
import shutil
import sys
from pathlib import Path

from engkit import __version__, installer, memory, platforms
from engkit.catalog import Skill, discover
from engkit.fsutil import check_no_symlinks
from engkit.resources import resource_origin

STATUS_LEVELS = {
    "identical": "info",
    "missing": "info",
    "differs": "warning",
    "empty": "warning",
    "unsafe": "error",
}
STATUS_LABELS = {
    "identical": "installed (matches canonical)",
    "missing": "not installed",
    "differs": "installed copy differs from canonical (conflict on install)",
    "empty": "empty directory (interrupted or in-progress install)",
    "unsafe": "unsafe or unreadable destination",
}


class Report:
    def __init__(self):
        self.data: dict = {"errors": 0, "warnings": 0, "sections": []}

    def add_section(self, title: str, items: list[tuple[str, str]]) -> None:
        entries = [{"level": level, "message": message} for level, message in items]
        self.data["sections"].append({"title": title, "items": entries})
        self.data["errors"] += sum(1 for level, _ in items if level == "error")
        self.data["warnings"] += sum(1 for level, _ in items if level == "warning")


def run(
    resource_root: Path,
    target: str,
    project_root: Path,
    home: Path | None,
    check_global: bool = True,
) -> dict:
    report = Report()
    report.add_section("Environment", _environment_items(resource_root, project_root))
    catalog = discover(resource_root)
    errors = [issue for issue in catalog.issues if issue.level == "error"]
    catalog_items = [("error", issue.format()) for issue in errors]
    names = ", ".join(skill.name for skill in catalog.skills)
    catalog_items.append(("info", f"{len(catalog.skills)} canonical skill(s): {names}"))
    report.add_section("Catalog", catalog_items)

    scopes = [("project", project_root)]
    if check_global and home is not None:
        scopes.append(("user", home))
    for platform in platforms.expand_target(target):
        items = _cli_items(platform)
        for scope, root in scopes:
            destination = platforms.destination(platform, scope, root)
            items.extend(_destination_items(destination, catalog.skills))
        report.add_section(f"Platform: {platform.display}", items)
        instructions = project_root / platform.instructions_file
        if instructions.exists():
            message = f"{platform.instructions_file} present (engkit never modifies it)"
            report.add_section(f"Instructions: {platform.instructions_file}", [("info", message)])
    report.add_section("Project memory", [memory.status(project_root)])
    return report.data


def _environment_items(resource_root: Path, project_root: Path) -> list[tuple[str, str]]:
    python_version = python_platform.python_version()
    return [
        ("info", f"engkit {__version__} on Python {python_version} ({sys.platform})"),
        ("info", f"resources: {resource_origin(resource_root)} ({resource_root})"),
        ("info", f"project root: {project_root}"),
    ]


def _cli_items(platform: platforms.Platform) -> list[tuple[str, str]]:
    executable = shutil.which(platform.cli)
    location = executable or "not found on PATH"
    items = [("info", f"{platform.display} CLI: {location} (not executed)")]
    if not executable:
        message = f"{platform.display} discovery not verifiable here (docs/manual-smoke-tests.md)"
        items.append(("warning", message))
    return items


def _destination_items(
    destination: platforms.Destination, skills: list[Skill]
) -> list[tuple[str, str]]:
    scope = destination.scope
    items = [
        ("error", f"{scope}: unsafe destination ({problem})")
        for problem in check_no_symlinks(destination.root, destination.parts)
    ]
    for skill in skills:
        target = destination.skill_path(skill.name)
        status = installer.status_of(skill.path, target)
        message = f"{scope}: {skill.name}: {STATUS_LABELS[status]} -> {target}"
        items.append((STATUS_LEVELS[status], message))
    for leftover in _leftover_staging(destination.skills_dir):
        message = f"{scope}: leftover staging directory {leftover} (safe to delete manually)"
        items.append(("warning", message))
    return items


def _leftover_staging(skills_dir: Path) -> list[Path]:
    if skills_dir.is_symlink() or not skills_dir.is_dir():
        return []
    try:
        entries = sorted(skills_dir.iterdir())
    except OSError:
        return []
    return [entry for entry in entries if installer.STAGE_MARKER in entry.name]


def home_dir() -> Path | None:
    try:
        return Path(os.path.expanduser("~")).resolve(strict=True)
    except OSError:
        return None
