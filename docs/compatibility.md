# Platform compatibility

This file separates what was **verified**, how, and when, from what is
**assumed**. Platform behavior changes, so re-check it on each release.

Verification date: 2026-10-09. Official documentation was read read-only in
task C0 (see "Slash commands (C0, 2026-10-09)" below). Agent-level behavior
(a real session discovering or invoking a skill) is still **pending**.

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
| User (`--global`) | `~/.claude/skills/<name>/` | `~/.agents/skills/<name>/` | Claude: as above. Codex: official docs (`$HOME/.agents/skills`); switched on 2026-10-09 by owner decision |

### Open questions (unverified assumptions)

- **Codex user scope (decided 2026-10-09):** the official Codex docs list the
  user scope as `$HOME/.agents/skills`, so `--global --target codex` installs
  there. The local 0.144.1 binary still mentions `$CODEX_HOME/skills`
  (`~/.codex/skills`), probably a legacy location; engkit no longer uses it.
  Whether Codex 0.144.1 reads `~/.agents/skills` is pending a live smoke test.
- **Codex repo scope lookup (verified, docs):** Codex scans `.agents/skills` in
  every directory from the cwd up to the repo root. Installing at the project
  root is therefore discovered from any subdirectory.
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
- **Invocation:** see the C0 table below. Claude Code: `/<name> text`; Codex:
  `/skills` or `$name`; both also select skills by description (docs).

## Built-in skill names

The validator rejects a skill whose name equals a built-in skill name of a
target platform, so an installed skill cannot shadow a built-in one. The lists are in
`BUILTIN_SKILL_NAMES` in `src/engkit/platforms.py`.

- **Claude Code:** 34 names. Bundled skills seen in the skill listing of
  Claude Code 2.1.295 sessions (for example `code-review`, `security-review`,
  `init`, `simplify`, `dataviz`) plus bundled skills and built-in slash commands
  named on the official commands page (for example `batch`, `debug`, `verify`,
  `review`, `plan`, `memory`, `bug`, `help`). Built-in command names are reserved
  even where a skill would technically shadow them, because `/name` would be
  confusing next to the built-in.
- **Codex:** 6 names: `openai-docs`, `skill-creator`, `skill-installer` (official
  docs and the 0.144.1 binary), `plugin-creator` and `imagegen` (binary only),
  and `plan` (docs only).

Re-check both lists on every release: built-ins change between platform versions.

## Slash commands (C0, 2026-10-09)

Labels: **verified (docs)**, **verified (local binary)**, **assumed/pending**.
Docs read: https://code.claude.com/docs/en/skills,
https://code.claude.com/docs/en/commands,
https://developers.openai.com/codex/skills (308-redirects to
https://learn.chatgpt.com/docs/build-skills). No session was run.

| # | Question | Answer | Label | Source |
|---|---|---|---|---|
| 1 | Claude: does `.claude/skills/<name>/SKILL.md` (project or `~/.claude/skills`) become `/<name>`? Unified with commands? | Yes, and skills and `.claude/commands/` are unified. The `name` field defaults to the directory name. | verified (docs) | skills page: "A file at `.claude/commands/deploy.md` and a skill at `.claude/skills/deploy/SKILL.md` both create `/deploy` and work the same way." Local binary mentions `.claude/skills/*/SKILL.md` in the project and `~/.claude/skills/*/SKILL.md`. A live `/` menu check is pending. |
| 2 | Claude: how does text after `/name` reach the skill? | `$ARGUMENTS` (all), `$ARGUMENTS[N]` / `$N` (0-based, shell-style quoting), named args via an `arguments:` list. If the body has no placeholder, Claude Code appends `ARGUMENTS: <value>`. | verified (docs); verified (local binary) | skills page: "When no placeholder receives an argument, Claude Code appends them as `ARGUMENTS: <value>`." Binary regex `\$ARGUMENTS\[\d+\]\|\$ARGUMENTS\|\$\d+` and the string `ARGUMENTS: `. Commands page: trailing text of `/skill-a /skill-b text` goes to each chained skill (max 6). |
| 3 | Claude: precedence for equal names | Enterprise > personal > project. A skill beats a `.claude/commands/` file of the same name. Plugin skills are namespaced `/plugin:skill` and do not collide. A user/project skill replaces a bundled skill or built-in command of the same name but NOT its aliases (project `code-review` skill replaces `/code-review`; alias `/review` still runs the built-in). | verified (docs) | skills page: "Enterprise over personal, and personal over project." and "A project `code-review` skill replaces `/code-review`, and the bundled alias `/review` never runs your skill." |
| 4 | Claude: command-relevant frontmatter; is `argument-hint` safe? | Documented: `name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context`, `agent`, `background`, `hooks`, `paths`, `shell`, `metadata`, `license`, `compatibility`. Unrecognized fields are ignored without error. `description` plus `when_to_use` is truncated at 1,536 chars in the listing. `argument-hint` is safe for Claude. For Codex, no doc says it is rejected or honored; Codex reads `name` and `description` (its own options live in `agents/openai.yaml`). Treat `argument-hint` as Claude-only and non-portable; the validator should keep warning on it or allow it as an explicitly listed Claude-only key. | verified (docs) for Claude; assumed/pending for Codex tolerance | skills page frontmatter table: "`argument-hint`: Autocomplete hint, e.g. `[issue-number]`." and "Unrecognized fields are ignored without an error." Codex page: "`SKILL.md` must include `name` and `description`." |
| 5 | Claude: built-in names that could collide with the command names | None of the six command names checked in C0 (`engineering-onboard`, `change-plan`, `change-review`, `bug-investigate`, `stack-select`, `memory-save`) appears on the official commands page; near names exist (`/plan`, `/memory`, `/review`, `/debug`, `/bug`, `/code-review`). No collision. `implement-plan` was added after C0: it is not in the reserved lists in `platforms.py`, but it was not checked against the commands page (pending; re-check on release). Bundled skills on that page: `artifact-capabilities`, `artifact-diagramming`, `batch`, `claude-api`, `claude-in-chrome`, `code-review`, `dataviz`, `debug`, `design`, `design-sync`, `doctor`, `fewer-permission-prompts`, `loop`, `run`, `run-skill-generator`, `simplify`, `slides`, `update-config`, `verify`, `workflow-authoring`. `plugin-authoring`, `init`, `security-review`, `schedule`, `keybindings-help` were seen in a session skill listing only. The binary was not searched for the six names. | verified (docs) for the page list; observed (session) for the session-only names | https://code.claude.com/docs/en/commands (entries tagged "Skill"). |
| 6 | Codex: explicit invocation; auto-selection? | `/skills` or type `$` to mention a skill (`$skill-name`). Codex also selects implicitly when the task matches the description; `agents/openai.yaml` `policy.allow_implicit_invocation: false` disables that (explicit `$skill` still works). | verified (docs); verified (local binary) | Codex page: "In Codex CLI or the IDE extension, run `/skills` or type `$` to mention a skill." and "Codex can choose a skill when your task matches the skill `description`." Binary: `policy.allow_implicit_invocation` must be a boolean; `SkillMention` input element. |
| 7 | Codex: user and repo paths | User: `$HOME/.agents/skills` (docs). Local binary also references `$CODEX_HOME/skills` / `~/.codex/skills` (skill-creator text, `.system` skills), so the legacy path likely still works (pending test). Repo: `.agents/skills` in every directory from cwd up to the repo root. Admin: `/etc/codex/skills`. Duplicate names are not merged; both appear in selectors (no precedence rule documented). | verified (docs); `~/.codex/skills` legacy status assumed/pending | Codex page: "Codex scans `.agents/skills` in every directory from your current working directory up to the repository root." User: `$HOME/.agents/skills`. Binary string: "place it in `$CODEX_HOME/skills` (or `~/.codex/skills` when `CODEX_HOME` is unset) so Codex can discover it automatically". |
| 8 | Codex: text after the invocation | Not documented. Mention is a structured `SkillMention` input element inside the user message, so the rest of the message is ordinary prompt text visible to the model alongside the skill. | assumed/pending | Docs silent. Binary has `SkillMention` among user-input elements. |
| 9 | Codex: frontmatter constraints | Docs require `name` and `description` and give no length limits. Local skill-creator tooling caps generated names at 64 characters (`max_name_length = 64 - len(suffix)`). Nothing documented stricter than the Agent Skills spec. | verified (docs: no limits stated); name cap 64 verified (local binary) | Codex page; binary string `max_name_length = 64 - len(suffix)`. |

Codex built-in/system skills seen: `skill-creator`, `skill-installer`,
`plugin-creator`, `imagegen` (under `.system`), and `openai-docs` (earlier
observation). Docs name skill-creator, plan and skill-installer.

### Consequences for engkit decisions

- (a) A skill `X` is invoked as `/X` in Claude Code: supported by docs.
- (b) User and model invocation both work: supported by docs on both platforms
  (disable with `disable-model-invocation` for Claude, `allow_implicit_invocation`
  for Codex).
- (c) Codex uses the same installed skill format; but the user path and the
  `$name` invocation syntax differ from the Claude `/name` form.

### Why `code-review` was renamed

engkit's `code-review` skill was renamed to `change-review`. Claude Code 2.1.295
ships a built-in `code-review` skill, so the names collided.

## Invoking commands

- **Claude Code: `/<name>` (verified, docs).** Skills installed under
  `.claude/skills/<name>/` become `/<name>`. A live `/` menu check is pending.
- **Codex: `$<name>` and `/skills` (verified, docs).** Type `/skills` to browse,
  or `$` to mention a skill. Codex also selects a skill by its description.
- **Argument passing in Codex: pending.** Whether text typed after `$<name>` is
  passed to the command is not documented. Commands must work without arguments.

## Project instruction files

engkit never edits `CLAUDE.md` or `AGENTS.md`. `engkit memory init` prints a
snippet for you to add yourself:

- `CLAUDE.md`: `@.engkit/memory/INDEX.md`. Claude Code's support for `@path`
  imports is documented Claude Code behavior as known at authoring time. It is
  **not re-verified** for 2.1.295.
- `AGENTS.md`: "Read .engkit/memory/INDEX.md at task start and open only the
  entries relevant to the task." No import mechanism is assumed for Codex.
