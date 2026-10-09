# engkit

engkit is a portable set of engineering-workflow commands for **Claude Code**
and **OpenAI Codex**, plus a small local CLI to install, update and diagnose
them. Each command is a skill (`SKILL.md`) that your agent runs on demand. The
commands also keep a small, local, project memory that both agents can read.

engkit is not an agent runtime, an MCP server or an LLM client. It never runs
the scripts that ship with a skill. Only `--source` commands use the network
(to fetch git sources you ask for; see [Security model](#security-model)).

## Quickstart

```bash
pipx install engkit          # or: uv tool install engkit, or: pip install engkit
cd my-project
engkit init                  # installs the commands for the agents found on PATH
```

Then open Claude Code in `my-project` and run:

```text
/engineering-onboard
```

It maps the project and records what it learns in `.engkit/memory/`. A typical
flow after that:

```text
/change-plan add rate limiting to the export API
/change-review
/bug-investigate checkout test fails on CI only
/memory-save
```

In Codex, type `$engineering-onboard` instead. Codex uses `$name` where Claude
Code uses `/name`.

`engkit init` installs every command for the platforms it finds on `PATH`
(`claude`, `codex`). It never runs them. Use `--target claude`, `--target codex`
or `--target all` to choose yourself. If neither agent is found, it exits with
code 2 and asks for `--target`. Running it again changes nothing.

Requirements: Python 3.11 or newer, Linux or macOS. PyYAML is the only runtime
dependency (installed automatically). `git` on `PATH` is needed only for
`--source` installs and for `update` of git-sourced commands.

## Commands

| Command | Purpose | Without arguments |
|---|---|---|
| `/engineering-onboard` | Map an existing project and record context in `.engkit/memory` | Maps the whole project. An argument limits it to a path or component |
| `/change-plan` | Plan a change before coding | Asks what to plan |
| `/change-review` | Review a change | Reviews uncommitted changes against HEAD. If the tree is clean, asks for a range or PR |
| `/bug-investigate` | Find the root cause of a bug | Asks for the symptom |
| `/stack-select` | Compare stacks for a new project or component | Asks for requirements |
| `/memory-save` | Record decisions, gotchas and unfinished work | Proposes entries from the session and writes only after you confirm. An argument saves that note |

Claude Code runs a command as `/name`. Codex runs it as `$name`. Type `/skills`
in Codex to browse the list. Both agents can also pick a command from its
description, so the model may run one without you typing its name.

Every command separates **verified fact**, **plausible hypothesis** and
**untested assumption**. None authorizes edits, production access or
destructive actions.

## Usage

### Install commands

`engkit init` is the normal way to start. The default scope is the project, and
`--project-dir` defaults to the current directory.

```bash
engkit init --project-dir ~/code/my-app                  # detected platforms
engkit init --project-dir ~/code/my-app --target claude  # one platform
engkit init --global --target codex                      # your user account
```

`init` creates `.engkit/memory/` for project scope. `--global` skips memory. It
prints a snippet for your `CLAUDE.md` or `AGENTS.md`. Add it yourself; engkit
never edits those files.

A conflicting command (a different copy already installed) is reported, the
other commands still install, and the exit code is nonzero. Nothing is
overwritten.

To install a single command, use `engkit install`:

```bash
engkit install bug-investigate --target claude --project-dir ~/code/my-app
engkit install change-review --target codex --project-dir ~/code/my-app
engkit install change-plan --target all --project-dir ~/code/my-app
```

Use `--global` instead of `--project-dir` to write to your user account
(`~/.claude/skills` and `~/.agents/skills`).

### Install commands from a git source

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
  installs the same commands.
- user scope (`--global`): `~/.engkit/skills.lock.json`.

### Update and remove

```bash
engkit update --target all --project-dir ~/code/my-app          # all locked commands
engkit update team-review --target claude --project-dir ~/code/my-app --yes   # git source
engkit uninstall team-review --target claude --project-dir ~/code/my-app
```

`update` refreshes every command recorded in the lockfile. `update` and
`uninstall` act only on installs whose files still match the lockfile hash. If
you edited a copy, engkit reports a conflict and leaves it alone. Move your
edits aside yourself, then update or reinstall.

### Project memory

```bash
engkit memory validate --project-dir ~/code/my-app
```

`.engkit/memory/` is local to each machine and is never committed (it has its
own `.gitignore`). Do not store secrets. `memory validate` warns on
secret-like strings but cannot prove there are none.

### Check the setup

```bash
engkit doctor --target all --project-dir ~/code/my-app
```

`doctor` is read-only. It reports installed commands, lockfile state and a
project memory status line.

### Where commands go

| Target | Project scope | User scope (`--global`) |
|---|---|---|
| `claude` | `<project>/.claude/skills/<name>/` | `~/.claude/skills/<name>/` |
| `codex` | `<project>/.agents/skills/<name>/` | `~/.agents/skills/<name>/` |

Installation copies files and never overwrites anything:

- An identical installed copy reports `already installed`.
- A different copy reports `conflict` (exit 3) and is left untouched.
- `--target all` reports each platform separately.

## Security model

- **Network scope.** Only three commands touch the network, and only for git
  sources: `list --source`, `install --source` and `update` of a git-sourced
  entry. They call the system `git` with a shallow fetch, no submodules, hooks
  disabled, `GIT_TERMINAL_PROMPT=0` and a timeout. Every other command runs
  locally. No telemetry, no LLM calls.
- **Preview before remote install.** `install --source` and `update` of a git
  source require `--yes` after the preview. The preview lists executable files
  and anything under `scripts/` so you can see them before anything is written.
- **Command files are never executed.** Scripts bundled in a skill are copied,
  not run.
- **No overwrites.** Installs are staged, validated and published without
  replacing existing files. Modified installs are never updated or removed.
- **Writes are limited to** the requested commands directory,
  `.engkit/skills.lock.json`, and `.engkit/memory/` (created by `init` only).
- **Never modifies** `CLAUDE.md`, `AGENTS.md`, IDE configs or git hooks.
- Rejects path traversal, absolute paths and symlinks that escape the toolkit
  root. Symlinked managed destination parents are rejected.
  Remaining concurrency limits are documented in
  [docs/adr/0002-installation-safety.md](https://github.com/trustius/engkit/blob/main/docs/adr/0002-installation-safety.md).

## Limitations

- **No live agent checks yet.** Command discovery (`/` and `$` menus), invocation
  and argument passing have not been checked in a live Claude Code or Codex
  session. Every row in
  [docs/manual-smoke-tests.md](https://github.com/trustius/engkit/blob/main/docs/manual-smoke-tests.md)
  is `pending`.
- **No eval results.** No eval case has been run. Outcomes are `not-run` in
  [evals/README.md](https://github.com/trustius/engkit/blob/main/evals/README.md).
- **Path mappings are partly unverified.** Claude Code paths match the official
  docs and the installed binary. Codex user scope (`~/.agents/skills`) follows
  the official docs; whether Codex 0.144.1 reads it is pending a live test. See
  [docs/compatibility.md](https://github.com/trustius/engkit/blob/main/docs/compatibility.md).
- **Codex argument passing is pending.** Whether text typed after `$name` reaches
  the command is not documented (see `docs/compatibility.md`).
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

- Canonical commands live in `src/engkit/skills/<name>/`. Edit them there; do not
  add per-platform copies.
- New commands: follow [docs/skill-authoring.md](https://github.com/trustius/engkit/blob/main/docs/skill-authoring.md)
  and add trigger evals in `evals/triggers/`. Other evals are described in
  [evals/README.md](https://github.com/trustius/engkit/blob/main/evals/README.md).
- Platform-specific behavior belongs only in `src/engkit/platforms.py`.
- Tests create temporary project and home directories. They never touch your
  real `~/.claude`, `~/.codex`, `~/.agents` or `~/.engkit`.
- Coding rules and invariants: [CLAUDE.md](https://github.com/trustius/engkit/blob/main/CLAUDE.md).
  Architecture decisions: [docs/adr/](https://github.com/trustius/engkit/blob/main/docs/adr/).

## Release

Releases follow [RELEASING.md](https://github.com/trustius/engkit/blob/main/RELEASING.md),
which holds the checklist (tests, lint, `engkit validate`, distribution test,
compatibility and smoke-test status, version bump in `pyproject.toml` and
`src/engkit/__init__.py`). Changes are listed in
[CHANGELOG.md](https://github.com/trustius/engkit/blob/main/CHANGELOG.md).

## License

MIT (see [LICENSE](https://github.com/trustius/engkit/blob/main/LICENSE)).
