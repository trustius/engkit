# engkit

engkit is a portable set of engineering-workflow skills (`SKILL.md`) for
**Claude Code** and **OpenAI Codex**, plus a small local CLI to list, validate,
install, update and diagnose them. It also keeps a small, local, project memory
that both agents can read.

engkit is not an agent runtime, an MCP server or an LLM client. It never runs
the scripts that ship with a skill. Network access is limited to fetching git
sources you ask for (see [Security model](#security-model)).

## Skills

| Skill | Use it when |
|---|---|
| `systematic-debugging` | A test fails, an error appears, or behavior is wrong or intermittent |
| `change-review` | A diff, PR or patch needs review |
| `implementation-planning` | A feature, migration, refactor or significant fix needs a plan before code |
| `project-discovery` | You are mapping an unfamiliar or multi-component repository |
| `stack-selection` | You are choosing a stack for a new project or component |
| `project-memory` | You want to recall or record project decisions, gotchas and conventions |

`change-review` was called `code-review` before. It was renamed because Claude
Code ships a built-in `code-review` skill (see `docs/compatibility.md`).

Every skill separates **verified fact**, **plausible hypothesis** and
**untested assumption**. None authorizes edits, production access or
destructive actions.

## Quickstart

Requirements: Python 3.10+. PyYAML 6 is the only runtime dependency.

```bash
git clone <this repo> engkit && cd engkit
python3 -m venv .venv
.venv/bin/pip install -e .          # fetches PyYAML if missing (needs network)
.venv/bin/engkit list
.venv/bin/engkit validate
```

Offline alternative, if your interpreter already has PyYAML:
`python3 -m venv --system-site-packages .venv && .venv/bin/pip install --no-index --no-deps --no-build-isolation -e .`
(see `docs/adr/0001-language-and-distribution.md`).

### Install a built-in skill into a project

The default scope is the project. `--project-dir` defaults to the current
directory.

```bash
.venv/bin/engkit install systematic-debugging --target claude --project-dir ~/code/my-app
.venv/bin/engkit install change-review --target codex --project-dir ~/code/my-app
.venv/bin/engkit install implementation-planning --target all --project-dir ~/code/my-app
```

Use `--global` instead of `--project-dir` to write to your user account
(`~/.claude/skills` and `~/.codex/skills`).

### Install skills from a git source

Remote installs always show a preview first. Nothing is written until you
repeat the command with `--yes`. The URL below is a placeholder.

```bash
# 1. Preview: prints URL, ref, resolved commit, file list and executable files. Writes nothing.
.venv/bin/engkit install --source https://example.test/team/skills.git \
  --skill change-review --target claude --project-dir ~/code/my-app

# 2. Install the previewed content. Pin --ref to a commit to guarantee it.
.venv/bin/engkit install --source https://example.test/team/skills.git --ref <commit> \
  --skill change-review --target claude --project-dir ~/code/my-app --yes
```

Accepted URLs: `https://`, `ssh://`, `user@host:path` and `file://`. Archives
(`.zip`, `.tar.gz`) are not supported. `git` must be on your `PATH`.

Installed sources are recorded in a lockfile:

- project scope: `<project>/.engkit/skills.lock.json`. Commit it so the team
  installs the same skills.
- user scope (`--global`): `~/.engkit/skills.lock.json`.

### Update and remove

```bash
.venv/bin/engkit update --target all --project-dir ~/code/my-app          # built-in skills
.venv/bin/engkit update change-review --target claude --project-dir ~/code/my-app --yes   # git source
.venv/bin/engkit uninstall change-review --target claude --project-dir ~/code/my-app
```

`update` and `uninstall` act only on installs whose files still match the
lockfile hash. If you edited a copy, engkit reports a conflict and leaves it
alone. Move your edits aside yourself, then update or reinstall.

### Project memory

```bash
.venv/bin/engkit memory init --project-dir ~/code/my-app
.venv/bin/engkit memory validate --project-dir ~/code/my-app
```

`memory init` creates `.engkit/memory/` with a `.gitignore` that ignores
everything and an `INDEX.md`. It never overwrites files. It prints two snippets
for you to add yourself to `CLAUDE.md` (`@.engkit/memory/INDEX.md`) and
`AGENTS.md`. engkit does not edit those files.

Memory is local to each machine and is never committed. Do not store secrets.

### Check the setup

```bash
.venv/bin/engkit doctor --target all --project-dir ~/code/my-app
```

`doctor` is read-only. It reports installed skills, lockfile state and a
project memory status line.

### Where skills go

| Target | Project scope | User scope (`--global`) |
|---|---|---|
| `claude` | `<project>/.claude/skills/<name>/` | `~/.claude/skills/<name>/` |
| `codex` | `<project>/.agents/skills/<name>/` | `~/.codex/skills/<name>/` |

Installation copies files and never overwrites anything:

- An identical installed copy reports `already installed`.
- A different copy reports `conflict` (exit 3) and is left untouched.
- `--target all` reports each platform separately.

To use a skill, ask for it by name ("use the change-review skill on this
diff"). Claude Code can also choose a skill from its description. To point
agents at a skill from your own instruction file, add a line to `CLAUDE.md` or
`AGENTS.md` yourself, for example: "For bugs, follow the systematic-debugging
skill." engkit never edits these files.

## Security model

- **Network scope.** Only three commands touch the network, and only for git
  sources: `list --source`, `install --source` and `update` of a git-sourced
  entry. They call the system `git` with a shallow fetch, no submodules, hooks
  disabled, `GIT_TERMINAL_PROMPT=0` and a timeout. Every other command is
  offline. No telemetry, no LLM calls.
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
  `docs/adr/0002-installation-safety.md`.

## Contributing

```bash
.venv/bin/pip install -e ".[dev]"                          # adds ruff for development
.venv/bin/python -m unittest discover -s tests -t .        # full suite (includes a wheel build)
.venv/bin/python -m unittest tests.test_installer          # one module
.venv/bin/python -m unittest tests.test_installer.InstallerTest.test_conflict_leaves_existing_untouched
ENGKIT_SKIP_DIST=1 .venv/bin/python -m unittest discover -s tests -t .   # skip the wheel test
.venv/bin/ruff check src tests
.venv/bin/ruff format src tests
.venv/bin/engkit validate
```

- Tests create temporary project and home directories. They never touch your
  real `~/.claude`, `~/.codex` or `~/.engkit`.
- New skills: follow `docs/skill-authoring.md` and add trigger evals in
  `evals/triggers/`. Other evals are described in `evals/README.md`.
- Platform-specific behavior belongs only in `src/engkit/platforms.py`.
- Current direction: `ENHANCEMENT_PLAN.md`. Architecture decisions: `docs/adr/`.
- Coding rules and invariants: `CLAUDE.md`.

## Limitations

- **No live agent checks.** Discovery, invocation and context use have not been
  checked in a live Claude Code or Codex session. Every row in
  `docs/manual-smoke-tests.md` is `pending`.
- **No eval results.** No eval case has been run. Outcomes are `not-run` in
  `evals/README.md`.
- **Path mappings come from local evidence.** Install destinations were checked
  against the installed CLI binaries, not current official docs. The Codex
  user-scope path is an open question (`docs/compatibility.md`).
- **No install `--force`.** Conflicting or modified installs must be moved
  aside by hand.
- **Git sources only.** Archives are not supported. Git sources need `git` on
  `PATH`.
- **Parent-directory race.** Installation does not protect against a hostile
  concurrent replacement of a parent directory (ADR 0002).
- **Windows is untested.**

## Release checklist

- [ ] `python -m unittest discover -s tests -t .` passes (record the output in `docs/test-results.md`)
- [ ] `ruff check src tests` and `ruff format --check src tests` pass
- [ ] `engkit validate` passes; `engkit list` shows all six skills
- [ ] Distribution test passed (wheel installed outside the checkout)
- [ ] `docs/compatibility.md` re-verified against current official docs; adapter updated if paths or built-in names changed
- [ ] Manual smoke tests run, or explicitly left pending, in `docs/manual-smoke-tests.md`
- [ ] Eval status updated with real outcomes only
- [ ] Version bumped in `pyproject.toml` and `src/engkit/__init__.py`

## License

MIT (see `LICENSE`).
