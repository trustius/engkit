"""Platform adapters: the only place mapping (platform, scope, root) to destinations."""

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
    "claude": Platform(
        "claude", "Claude Code", "claude", (".claude", "skills"), (".claude", "skills"), "CLAUDE.md"
    ),
    "codex": Platform(
        "codex", "Codex", "codex", (".agents", "skills"), (".agents", "skills"), "AGENTS.md"
    ),
}


# Names a canonical skill must not use. Claude: bundled skills observed in Claude Code 2.1.295
# sessions plus built-in slash commands from the official docs (2026-10-09). Codex: system
# skills named in the official docs or seen in the codex 0.144.1 binary (`plan` is docs-only).
# See docs/compatibility.md.
BUILTIN_SKILL_NAMES = {
    "claude": frozenset(
        {
            "artifact-capabilities",
            "artifact-diagramming",
            "batch",
            "bug",
            "claude-api",
            "claude-in-chrome",
            "code-review",
            "compact",
            "config",
            "context",
            "dataviz",
            "debug",
            "design",
            "design-sync",
            "doctor",
            "fewer-permission-prompts",
            "help",
            "init",
            "keybindings-help",
            "loop",
            "memory",
            "plan",
            "plugin-authoring",
            "review",
            "run",
            "run-skill-generator",
            "schedule",
            "security-review",
            "simplify",
            "skills",
            "slides",
            "update-config",
            "verify",
            "workflow-authoring",
        }
    ),
    "codex": frozenset(
        {"imagegen", "openai-docs", "plan", "plugin-creator", "skill-creator", "skill-installer"}
    ),
}


def builtin_collisions(name: str) -> list[str]:
    """Platform ids whose built-in skills already use ``name``."""
    return [platform_id for platform_id in PLATFORMS if name in BUILTIN_SKILL_NAMES[platform_id]]


def get(platform_id: str) -> Platform:
    try:
        return _REGISTRY[platform_id]
    except KeyError:
        choices = ", ".join(TARGET_CHOICES)
        raise ValueError(f"unknown target '{platform_id}' (choose from: {choices})") from None


def expand_target(target: str) -> list[Platform]:
    if target == "all":
        return [_REGISTRY[platform_id] for platform_id in PLATFORMS]
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
