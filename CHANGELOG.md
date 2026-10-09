# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - Unreleased

### Added

- Seven slash commands, each a skill that runs as `/<name>` in Claude Code and
  `$<name>` in Codex:
  - `/engineering-onboard`: map an existing project and record context in `.engkit/memory`.
  - `/plan-implement`: plan a change before coding.
  - `/change-review`: review a change (uncommitted changes against HEAD by default).
  - `/bug-investigate`: find the root cause of a bug.
  - `/stack-select`: compare stacks for a new project or component.
  - `/memory-save`: record decisions, gotchas and unfinished work, after confirmation.
  - `/implement-plan`: build one slice of a plan, with one approval per session.
- `engkit init [--project-dir PATH | --global] [--target claude|codex|all]`:
  installs every command for the platforms found on `PATH` (or for `--target`),
  creates `.engkit/memory/` for project scope, and prints the `CLAUDE.md` /
  `AGENTS.md` snippet. A rerun changes nothing.
- CLI commands: `list`, `validate`, `init`, `install` (built-in commands and
  `--source` git URLs, with a preview that requires `--yes`), `update`,
  `uninstall`, `doctor`, and `memory validate`.
- `.engkit/skills.lock.json` lockfile recording installed sources and content hashes.
- Safety properties: installs are staged and never overwrite existing files;
  skill files (including bundled scripts) are never executed; `update` and
  `uninstall` only touch installs whose files still match the lockfile.
- Shared guardrails in every command: plans of two or more steps go to
  `docs/plans/YYYY-MM-DD-<slug>.md` (never overwritten), nothing runs automatically
  on server environments, sensitive data is redacted, and work proceeds in small
  checked steps. `engkit validate` fails a skill that lacks them verbatim.
- `/plan-implement` always writes a plan file to `docs/plans/`; `/stack-select` writes one
  after an option is chosen; `/bug-investigate` writes one when the fix needs more than
  one change.
- Scenario evals for the shared guardrails in `evals/rules/`.
- `/implement-plan` (`$implement-plan` in Codex): builds one slice of a plan in
  `docs/plans/` per run. It shows the slice, its files and the verification commands
  of all remaining slices, then runs only the commands you approve for the session
  (one yes per session). It edits only the files the slice names and records the
  result in the plan's `## Progress` table, then stops until you say `continue`.
  Without an argument, it lists incomplete plans and asks which one. It never
  commits, pushes or switches branches.
- `/plan-implement` requires each slice's verification to be a command (argv and cwd) or
  a named manual check, and suggests `/implement-plan <plan file>` as its next step.
- Authorization wording in the skill-authoring contract: no skill edits files without an
  explicit request (`/implement-plan` only after your session approval), and no skill
  authorizes production access or destructive actions.

[0.1.0]: https://github.com/trustius/engkit/releases/tag/v0.1.0
