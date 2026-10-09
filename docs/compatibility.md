# Platform compatibility

This file separates what was **verified**, how, and when, from what is
**assumed**. Platform behavior changes, so re-check it on each release.

Verification date: 2026-10-09. Network access was not used. Official
documentation was **not** re-read for this release, and that check is pending.

## Installed versions inspected locally

| Platform | Version | How inspected |
|---|---|---|
| Claude Code | 2.1.295 | `claude --version`; `strings` on the installed binary; skill listing of a session |
| Codex CLI | 0.144.1 | `codex --version`; `strings` on the installed binary |

Neither CLI was used to run a prompt. Agent-level discovery and invocation
are **pending** (see `manual-smoke-tests.md`).

## Destination mapping (adapter: `src/engkit/platforms.py`)

| Scope | Claude Code | Codex | Evidence |
|---|---|---|---|
| Project | `<project>/.claude/skills/<name>/` | `<project>/.agents/skills/<name>/` | Claude: `.claude/skills` strings in the binary, plus the documented behavior known at authoring time. Codex: the binary contains `.agents` + `skills` path joins next to "failed to read skills directory" |
| User (`--global`) | `~/.claude/skills/<name>/` | `~/.codex/skills/<name>/` | Claude: as above. Codex: the binary contains `/.codex/skills` |

### Open questions (unverified assumptions)

- **Codex user scope:** recent Codex builds may also read `$HOME/.agents/skills`.
  The binary contains `.agents`/`skills` joins that could apply to both repo
  and home scopes. engkit keeps `~/.codex/skills` until a manual smoke test or
  the official docs confirm otherwise. If they differ, change only the codex
  user path in `platforms.py`.
- **Codex repo scope lookup:** whether Codex reads `.agents/skills` only at the
  repo root or also in parent and current directories is unverified. engkit
  installs at the project root you pass.
- **Symlinks:** engkit installs copies only, so platform symlink handling does
  not matter.
- **Naming limits:** engkit enforces the portable Agent Skills rules. Names
  are 1–64 characters of `[a-z0-9-]` with no leading, trailing or doubled
  hyphen, and must match the directory. Descriptions are 1–1024 characters.
  Both platforms are believed to accept this subset; per-platform stricter
  limits are unverified.
- **Frontmatter:** the shared skills use only `name` and `description`. The
  validator warns on other keys. The Codex binary mentions an optional
  `SKILL.json` interface file; engkit does not generate one.
- **Invocation:** Claude Code loads skills by description match or explicitly
  by name. Codex lists skills and reads `SKILL.md` on demand (from binary
  strings). The exact invocation syntax is unverified for both.

## Built-in skill names

The validator rejects a skill whose name equals a built-in skill name of a
target platform, so an installed skill cannot shadow a built-in one. The lists are in
`BUILTIN_SKILL_NAMES` in `src/engkit/platforms.py`.

- **Claude Code (observed):** the list in the code was taken from the skill
  listing of a Claude Code 2.1.295 session on 2026-10-09. It contains
  `code-review`, `security-review`, `init`, `simplify`, `loop`, `schedule`,
  `run`, `update-config`, `keybindings-help`, `fewer-permission-prompts`,
  `claude-api`, `plugin-authoring`, `workflow-authoring`, `review` and
  `skill-creator`. Built-in skills can change between releases, so re-observe
  this list on each release.
- **Codex (unverified):** only `openai-docs` was seen in the Codex binary
  strings. The code also lists `skill-creator` and `skill-installer`. Neither
  was confirmed in a session, so treat the Codex list as an assumption.

### Why `code-review` was renamed

engkit's `code-review` skill was renamed to `change-review`. Claude Code 2.1.295
ships a built-in `code-review` skill, so the names collided.

## Project instruction files

engkit never edits `CLAUDE.md` or `AGENTS.md`. `engkit memory init` prints a
snippet for you to add yourself:

- `CLAUDE.md`: `@.engkit/memory/INDEX.md`. Claude Code's support for `@path`
  imports is documented Claude Code behavior as known at authoring time. It is
  **not re-verified** for 2.1.295.
- `AGENTS.md`: "Read .engkit/memory/INDEX.md at task start and open only the
  entries relevant to the task." No import mechanism is assumed for Codex.
