"""Platform adapters: the only place mapping (platform, scope, root) to destinations.

See docs/compatibility.md for the evidence behind each mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PLATFORMS = ("claude", "codex")
TARGET_CHOICES = PLATFORMS + ("all",)


@dataclass(frozen=True)
class Platform:
    id: str
    display: str
    cli: str  # executable name, only looked up (never run) by doctor
    project_parts: tuple[str, ...]  # skills directory relative to the project root
    user_parts: tuple[str, ...]  # skills directory relative to the home directory
    instructions_file: str  # project instruction file (never modified by engkit)


_REGISTRY = {
    "claude": Platform("claude", "Claude Code", "claude", (".claude", "skills"), (".claude", "skills"), "CLAUDE.md"),
    "codex": Platform("codex", "Codex", "codex", (".agents", "skills"), (".codex", "skills"), "AGENTS.md"),
}


def get(platform_id: str) -> Platform:
    try:
        return _REGISTRY[platform_id]
    except KeyError:
        raise ValueError(f"unknown target '{platform_id}' (choose from: {', '.join(TARGET_CHOICES)})") from None


def expand_target(target: str) -> list[Platform]:
    if target == "all":
        return [_REGISTRY[p] for p in PLATFORMS]
    return [get(target)]


@dataclass(frozen=True)
class Destination:
    platform: Platform
    scope: str  # "project" | "user"
    root: Path  # resolved project root or home directory
    parts: tuple[str, ...]  # managed path below root, ending at the skills dir

    @property
    def skills_dir(self) -> Path:
        return self.root.joinpath(*self.parts)

    def skill_path(self, name: str) -> Path:
        return self.skills_dir / name


def destination(platform: Platform, scope: str, root: Path) -> Destination:
    if scope == "project":
        return Destination(platform, scope, root, platform.project_parts)
    if scope == "user":
        return Destination(platform, scope, root, platform.user_parts)
    raise ValueError(f"unknown scope '{scope}'")
