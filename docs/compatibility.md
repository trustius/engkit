# Platform compatibility

This file separates what was **verified**, how, and when, from what is
**assumed**. Platform behavior changes, so re-check it on each release.

Verification date: 2026-10-09. Network access was not used. Official
documentation was **not** re-read for this release, and that check is pending.

## Installed versions inspected locally

| Platform | Version | How inspected |
|---|---|---|
| Claude Code | 2.1.295 | `claude --version`; `strings` on the installed binary |
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
  and home scopes. engkit keeps `~/.codex/skills` (from the plan) until a
  manual smoke test or the official docs confirm otherwise. If they differ,
  change only `user_parts` for codex in `platforms.py`.
- **Codex repo scope lookup:** whether Codex reads `.agents/skills` only at the
  repo root or also in parent and current directories is unverified. engkit
  installs at the project root you pass.
- **Symlinks:** engkit installs copies only, so platform symlink handling does
  not matter for the MVP.
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

## Project instruction files

engkit never edits `CLAUDE.md` or `AGENTS.md`. `project generate --target`
writes **drafts** to `.engkit/generated/platform/{claude,codex}.md`:

- The Claude draft notes that `CLAUDE.md` supports `@path` imports. This is
  documented Claude Code behavior as known at authoring time and not
  re-verified for 2.1.295.
- The Codex draft references the context by path and does not rely on an
  import syntax, because no `AGENTS.md` import mechanism is assumed.
