"""Read-only diagnostics. Never repairs, recovers, installs or deletes anything."""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path

from engkit import __version__, generation, installer, platforms, resolution
from engkit.catalog import discover
from engkit.fsutil import check_no_symlinks
from engkit.resources import resource_origin


def run(resource_root: Path, target: str, project_root: Path, home: Path | None, check_global: bool = True) -> dict:
    report: dict = {"errors": 0, "warnings": 0, "sections": []}

    def section(title: str, items: list[tuple[str, str]]):
        report["sections"].append({"title": title, "items": [{"level": lvl, "message": msg} for lvl, msg in items]})
        report["errors"] += sum(1 for lvl, _ in items if lvl == "error")
        report["warnings"] += sum(1 for lvl, _ in items if lvl == "warning")

    section("Environment", [
        ("info", f"engkit {__version__} on Python {platform.python_version()} ({sys.platform})"),
        ("info", f"resources: {resource_origin(resource_root)} ({resource_root})"),
        ("info", f"project root: {project_root}"),
    ])

    catalog = discover(resource_root)
    items = [("error", i.format()) for i in catalog.issues if i.level == "error"]
    items.append(("info", f"{len(catalog.skills)} canonical skill(s): {', '.join(s.name for s in catalog.skills)}"))
    section("Catalog", items)

    for plat in platforms.expand_target(target):
        items = []
        cli = shutil.which(plat.cli)
        items.append(("info", f"{plat.display} CLI: {cli or 'not found on PATH'} (not executed)"))
        if not cli:
            items.append(("warning", f"{plat.display} discovery and invocation cannot be verified here; see docs/manual-smoke-tests.md"))
        scopes = [("project", project_root)]
        if check_global and home is not None:
            scopes.append(("user", home))
        for scope, root in scopes:
            dest = platforms.destination(plat, scope, root)
            for problem in check_no_symlinks(root, dest.parts):
                items.append(("error", f"{scope}: unsafe destination ({problem})"))
            for skill in catalog.skills:
                state = installer.status_of(skill.path, dest.skill_path(skill.name))
                level = {"identical": "info", "missing": "info", "differs": "warning", "empty": "warning", "unsafe": "error"}[state]
                label = {"identical": "installed (matches canonical)", "missing": "not installed",
                         "differs": "installed copy differs from canonical (conflict on install)",
                         "empty": "empty directory (interrupted or in-progress install)",
                         "unsafe": "unsafe destination (symlink or special file)"}[state]
                items.append((level, f"{scope}: {skill.name}: {label} -> {dest.skill_path(skill.name)}"))
            if dest.skills_dir.is_dir() and not dest.skills_dir.is_symlink():
                leftovers = sorted(p.name for p in dest.skills_dir.iterdir() if installer.STAGE_MARKER in p.name)
                for name in leftovers:
                    items.append(("warning", f"{scope}: leftover staging directory {dest.skills_dir / name} (safe to delete manually)"))
        section(f"Platform: {plat.display}", items)

    for plat in platforms.expand_target(target):
        if (project_root / plat.instructions_file).exists():
            section(f"Instructions: {plat.instructions_file}", [("info", f"{plat.instructions_file} present (engkit never modifies it)")])

    state = resolution.inspect_project(project_root, resource_root)
    items = []
    if state.resolved.explicit_present:
        items.append(("info", f"explicit profile: {resolution.PROFILE_REL}"))
    else:
        items.append(("info", "no explicit profile; detection only (engkit project define to add one)"))
    for d in state.resolved.diagnostics + state.registry.diagnostics + state.pack_resolution.diagnostics:
        items.append((d.level, d.format(with_level=False)))
    for comp in state.resolved.profile["components"]:
        for note in comp.get("unresolved") or []:
            items.append(("warning", f"[{comp['id']}] unresolved: {note}"))
    section("Project profile and packs", _dedupe(items))

    fresh = generation.freshness(project_root, resource_root)
    level = {"fresh": "info", "absent": "info", "stale": "warning", "modified": "warning",
             "incomplete": "error", "unsafe": "error"}.get(fresh["status"], "warning")
    items = [(level, f"generated context: {fresh['status']}")] + [(level, m) for m in fresh.get("messages", [])]
    if fresh.get("lock"):
        items.append(("warning", fresh["lock"]))
    backups = project_root / generation.BACKUPS_REL
    if backups.is_dir() and not backups.is_symlink():
        count = len([p for p in backups.iterdir() if not p.name.startswith(".")])
        items.append(("info", f"{count} generation backup(s) retained in {generation.BACKUPS_REL} (removed only by you)"))
    section("Generated context", items)
    report["generated_status"] = fresh["status"]
    return report


def _dedupe(items):
    seen, out = set(), []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def home_dir() -> Path | None:
    try:
        return Path(os.path.expanduser("~")).resolve(strict=True)
    except OSError:
        return None
