# engkit

engkit is a portable set of engineering-workflow skills (`SKILL.md`) for
**Claude Code** and **OpenAI Codex**, plus a small local CLI to list, validate,
install, update and diagnose them. It also keeps a small, local, project memory
that both agents can read.

engkit is not an agent runtime, an MCP server or an LLM client. It never runs
the scripts that ship with a skill. Only `--source` commands use the network
(to fetch git sources you ask for; see [Security model](#security-model)).

## Install

```bash
pipx install engkit
# or
uv tool install engkit
# or
pip install engkit
```

Then check the install and try it out:

```bash
engkit --version
engkit list
engkit install change-review --target claude --project-dir .
```

`change-review` is the skill name. `code-review` is a built-in name in Claude
Code, so engkit does not use it.

### Requirements

- Python 3.11 or newer.
- PyYAML is the only runtime dependency (installed automatically).
- `git` on `PATH` is required only for `--source` installs and for `update` of
  git-sourced skills.
- Linux and macOS only. Windows is not supported.

## Skills

| Skill | Use it when |
|---|---|
| `bug-investigate` | A test fails, an error appears, or behavior is wrong or intermittent |
| `change-review` | A diff, PR or patch needs review |
| `change-plan` | A feature, migration, refactor or significant fix needs a plan before code |
| `engineering-onboard` | You are mapping an unfamiliar or multi-component repository |
| `stack-select` | You are choosing a stack for a new project or component |
| `memory-save` | You want to recall or record project decisions, gotchas and conventions |

`change-review` was called `code-review` before. It was renamed because Claude
Code ships a built-in `code-review` skill (see
[docs/compatibility.md](https://github.com/trustius/engkit/blob/main/docs/compatibility.md)).

Every skill separates **verified fact**, **plausible hypothesis** and
**untested assumption**. None authorizes edits, production access or
destructive actions.

## Usage

### Install a built-in skill into a project

The default scope is the project. `--project-dir` defaults to the current
directory.

```bash
engkit install bug-investigate --target claude --project-dir ~/code/my-app
engkit install change-review --target codex --project-dir ~/code/my-app
engkit install change-plan --target all --project-dir ~/code/my-app
```

Use `--global` instead of `--project-dir` to write to your user account
(`~/.claude/skills` and `~/.agents/skills`).

### Install skills from a git source

Remote installs always show a preview first. Nothing is written until you
repeat the command with `--yes`. The URL below is a placeholder.

```bash
# 1. Preview: prints URL, ref, resolved commit, file list and executable files. Writes nothing.
engkit install --source https://example.test/team/skills.git \
  --skill team-review --target claude --project-dir ~/code/my-app

# 2. Install the previewed content. Pin --ref to a commit to guarantee it.
engkit install --source https://example.test/team/skills.git --ref <commit> \
  --skill team-review --target claude --project-dir ~/code/my-app --yes
```

Accepted URLs: `https://`, `ssh://`, `user@host:path` and `file://`. Archives
(`.zip`, `.tar.gz`) are not supported. `git` must be on your `PATH`.

Installed sources are recorded in a lockfile:

- project scope: `<project>/.engkit/skills.lock.json`. Commit it so the team
  installs the same skills.
- user scope (`--global`): `~/.engkit/skills.lock.json`.

### Update and remove

```bash
engkit update --target all --project-dir ~/code/my-app          # built-in skills
engkit update team-review --target claude --project-dir ~/code/my-app --yes   # git source
engkit uninstall team-review --target claude --project-dir ~/code/my-app
```

`update` and `uninstall` act only on installs whose files still match the
lockfile hash. If you edited a copy, engkit reports a conflict and leaves it
alone. Move your edits aside yourself, then update or reinstall.

### Project memory

```bash
engkit memory init --project-dir ~/code/my-app
engkit memory validate --project-dir ~/code/my-app
```

`memory init` creates `.engkit/memory/` with a `.gitignore` that ignores
everything and an `INDEX.md`. It never overwrites files. It prints two snippets
for you to add yourself to `CLAUDE.md` (`@.engkit/memory/INDEX.md`) and
`AGENTS.md`. engkit does not edit those files.

Memory is local to each machine and is never committed. Do not store secrets.

### Check the setup

```bash
engkit doctor --target all --project-dir ~/code/my-app
```

`doctor` is read-only. It reports installed skills, lockfile state and a
project memory status line.

### Where skills go

| Target | Project scope | User scope (`--global`) |
|---|---|---|
| `claude` | `<project>/.claude/skills/<name>/` | `~/.claude/skills/<name>/` |
| `codex` | `<project>/.agents/skills/<name>/` | `~/.agents/skills/<name>/` |

Installation copies files and never overwrites anything:

- An identical installed copy reports `already installed`.
- A different copy reports `conflict` (exit 3) and is left untouched.
- `--target all` reports each platform separately.

To use a skill, ask for it by name ("use the change-review skill on this
diff"). Claude Code can also choose a skill from its description. To point
agents at a skill from your own instruction file, add a line to `CLAUDE.md` or
`AGENTS.md` yourself, for example: "For bugs, follow the bug-investigate
skill." engkit never edits these files.

## Security model

- **Network scope.** Only three commands touch the network, and only for git
  sources: `list --source`, `install --source` and `update` of a git-sourced
  entry. They call the system `git` with a shallow fetch, no submodules, hooks
  disabled, `GIT_TERMINAL_PROMPT=0` and a timeout. Every other command runs
  locally. No telemetry, no LLM calls.
- **Preview before remote install.** `install --source` and `update` of a git
  source require `--yes` after the preview. The preview lists executable files
  and anything under `scripts/` so you can see them before anything is written.
- **Skill files are never executed.** Scripts bundled in a skill are copied, not run.
- **No overwrites.** Installs are staged, validated and published without
  replacing existing files. Modified installs are never updated or removed.
- **Writes are limited to** the requested skills directory, `.engkit/skills.lock.json`,
  and `.engkit/memory/` (created by `memory init` only).
- **Never modifies** `CLAUDE.md`, `AGENTS.md`, IDE configs or git hooks.
- Rejects path traversal, absolute paths and symlinks that escape the toolkit
  root. Symlinked managed destination parents are rejected.
  Remaining concurrency limits are documented in
  [docs/adr/0002-installation-safety.md](https://github.com/trustius/engkit/blob/main/docs/adr/0002-installation-safety.md).

## Limitations

- **No live agent checks.** Discovery, invocation and context use have not been
  checked in a live Claude Code or Codex session. Every row in
  [docs/manual-smoke-tests.md](https://github.com/trustius/engkit/blob/main/docs/manual-smoke-tests.md)
  is `pending`.
- **No eval results.** No eval case has been run. Outcomes are `not-run` in
  [evals/README.md](https://github.com/trustius/engkit/blob/main/evals/README.md).
- **Path mappings come from local evidence.** Install destinations were checked
  against the installed CLI binaries, not current official docs. The Codex
  user-scope path is an open question
  ([docs/compatibility.md](https://github.com/trustius/engkit/blob/main/docs/compatibility.md)).
- **No install `--force`.** Conflicting or modified installs must be moved
  aside by hand.
- **Git sources only.** Archives are not supported. Git sources need `git` on
  `PATH`.
- **Parent-directory race.** Installation does not protect against a hostile
  concurrent replacement of a parent directory (ADR 0002).
- **Linux and macOS only.** Windows is not supported.

## From source / contributing

```bash
git clone https://github.com/trustius/engkit.git && cd engkit
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m unittest discover -s tests -t .
```

- Canonical skills live in `src/engkit/skills/<name>/`. Edit them there; do not
  add per-platform copies.
- New skills: follow [docs/skill-authoring.md](https://github.com/trustius/engkit/blob/main/docs/skill-authoring.md)
  and add trigger evals in `evals/triggers/`. Other evals are described in
  [evals/README.md](https://github.com/trustius/engkit/blob/main/evals/README.md).
- Platform-specific behavior belongs only in `src/engkit/platforms.py`.
- Tests create temporary project and home directories. They never touch your
  real `~/.claude`, `~/.codex` or `~/.engkit`.
- Coding rules and invariants: [CLAUDE.md](https://github.com/trustius/engkit/blob/main/CLAUDE.md).
  Direction: [ENHANCEMENT_PLAN.md](https://github.com/trustius/engkit/blob/main/ENHANCEMENT_PLAN.md).
  Architecture decisions: [docs/adr/](https://github.com/trustius/engkit/blob/main/docs/adr/).

## Release

Releases follow [RELEASING.md](https://github.com/trustius/engkit/blob/main/RELEASING.md),
which holds the checklist (tests, lint, `engkit validate`, distribution test,
compatibility and smoke-test status, version bump in `pyproject.toml` and
`src/engkit/__init__.py`). Changes are listed in
[CHANGELOG.md](https://github.com/trustius/engkit/blob/main/CHANGELOG.md).

## License

MIT (see [LICENSE](https://github.com/trustius/engkit/blob/main/LICENSE)).
