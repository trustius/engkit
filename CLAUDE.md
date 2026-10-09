# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state and commands

engkit is a Python ≥3.10 package with one runtime dependency, PyYAML. The
current direction, including what was removed and why, is in
`ENHANCEMENT_PLAN.md`. Read it before starting a task. Older milestone sections
in `IMPLEMENTATION_PLAN.md` are partly superseded, as noted at its top.

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # needs network for PyYAML and ruff

.venv/bin/python -m unittest discover -s tests -t .          # full suite (includes a wheel build)
.venv/bin/python -m unittest tests.test_installer            # one module
.venv/bin/python -m unittest tests.test_installer.InstallerTest.test_conflict_leaves_existing_untouched   # one test
ENGKIT_SKIP_DIST=1 .venv/bin/python -m unittest discover -s tests -t .   # skip the wheel test

.venv/bin/ruff check src tests                               # lint
.venv/bin/ruff format src tests                              # format (check with --check)
.venv/bin/engkit validate                                    # skill lint
```

Layout: `src/engkit/` contains `cli` (argument parsing and output only),
`catalog`, `validator`, `platforms` (the only place that maps platform and scope
to paths), `installer`, `sources`, `lockfile`, `memory`, `fsutil`, `resources`,
`doctor` and `errors`. The only packaged resources are `skills/`, copied into
the built package by `setup.py`. Design decisions are in `docs/adr/`. Pytest
also works and is limited to `tests/` by `pyproject.toml`.

Commands:

- `engkit list [--json] [--source URL [--ref REF] [--path DIR]]`
- `engkit validate [NAME]`
- `engkit install NAME --target {claude,codex,all} [--project-dir P | --global]`
- `engkit install --source URL [--ref REF] [--path DIR] --skill A [--skill B] --target T [--project-dir P | --global] [--yes]`
- `engkit update [NAME] [--target T] [--project-dir P | --global] [--yes]`
- `engkit uninstall NAME --target T [--project-dir P | --global]`
- `engkit doctor [--target T] [--project-dir P] [--project-only] [--json]`
- `engkit memory init [--project-dir P]`
- `engkit memory validate [--project-dir P]`

Read `IMPLEMENTATION_PLAN.md` and `ENHANCEMENT_PLAN.md` before starting any task.
After a milestone-sized change, report the files changed, the commands run and
their results, any unresolved risks, and the next tasks.

## What engkit is

engkit is a portable library of engineering-workflow skills (`SKILL.md`) plus a
small local CLI for **Claude Code and OpenAI Codex**. It installs skills from
the built-in `skills/` directory or from a git source, keeps a lockfile, and
manages a local, platform-neutral project memory. It is not an agent runtime,
an MCP integration or an LLM client.

Concerns that stay separate:

1. **Skills** (`skills/<name>/SKILL.md`): stack-neutral workflows. Built-in
   skills: `systematic-debugging`, `change-review`, `implementation-planning`,
   `project-discovery`, `stack-selection`, `project-memory`.
2. **Platform adapters** (`platforms.py`): the only place that maps
   `(platform, scope, root)` to destination paths.
3. **Lockfile** (`skills.lock.json`): what was installed, from where, at which
   commit, with which content hash.
4. **Project memory** (`.engkit/memory/`): local notes shared by the agents of
   one project. See the invariants below.

Install destinations (verify against current official docs and record any
difference in `docs/compatibility.md`):

| Scope | Claude Code | Codex |
|---|---|---|
| Project | `<project>/.claude/skills/<name>/` | `<project>/.agents/skills/<name>/` |
| User (`--global`) | `~/.claude/skills/<name>/` | `~/.codex/skills/<name>/` |

## Invariants (must not be violated)

- **Single canonical source:** `skills/<name>/` is authoritative. Never commit per-platform copies. Keep platform-specific behavior in `platforms.py` only.
- **Skill names** use lower-case ASCII letters, digits and hyphens, must equal the directory name, and must not collide with a platform built-in skill name (`BUILTIN_SKILL_NAMES` in `platforms.py`). Reject traversal, absolute paths, and symlinks that escape the toolkit root.
- **Install is copy-based, staged and atomic:** copy to a temp sibling, validate, then publish with the no-replace contract in ADR 0002. A preflight check followed by an unconditional rename is insufficient. An identical destination reports `already installed`; a differing one reports `conflict` (exit 3) and is left untouched. Reject symlinked managed destination parents and clean only operation-owned staging.
- **Never overwrite or delete a modified install.** `update` and `uninstall` act only on lock-managed installs whose content hash equals the lock. A modified install is a conflict and is not touched.
- **Remote installs need a preview and `--yes`.** Without `--yes`, `install --source` prints the URL, ref, resolved commit, file list and executable files and writes nothing. `update` of a git-sourced entry shows old→new commit and needs `--yes`. Pin `--ref <commit>` to guarantee the previewed content.
- **Network only in `list --source`, `install --source` and `update`** (git-sourced entries). These call the system `git` with a shallow fetch, no submodules, hooks disabled, `GIT_TERMINAL_PROMPT=0` and a timeout. Every other command is offline. Do not add network access anywhere else without explicit user permission.
- **Memory is local, uncommitted and secret-free.** `.engkit/memory/` has its own `.gitignore` (`*`). Never store secrets, credentials or personal data. `memory validate` warns on secret-like strings; it does not prove absence.
- **Memory is not a log.** Do not record the same fact in Claude Code auto memory and in engkit memory. Record only what code and git history cannot show.
- **Default scope is project** (`--project-dir` or cwd). Global scope requires `--global`.
- **Never auto-modify** existing `CLAUDE.md`, `AGENTS.md`, IDE configs or git hooks. engkit prints snippets; the user adds them.
- **Never execute** scripts bundled in skills. Skill files are read and copied, never run.
- **Tests use temp home and project dirs only.** Never touch the real `~/.claude`, `~/.codex` or `~/.engkit`.
- **Use a real YAML parser** (`yaml.safe_load` / `safe_dump`). Do not hand-roll YAML. Otherwise prefer the standard library. PyYAML is the only runtime dependency.
- **No new dependencies, network calls, telemetry or package installs** without explicit user approval.
- **Honest reporting:** do not claim a test passed unless it ran. When Claude Code or Codex cannot be run locally, mark end-to-end checks as pending. Evals must never contain invented scores, and fixtures must be synthetic.

## Coding rules

- Full names, no abbreviations, except `i`, `path` and `exc`.
- Functions ≤40 lines and nesting ≤2 levels. Use early returns.
- No nested comprehensions and no nested ternaries.
- Comments only for non-obvious *why*. Docstrings are one line at most.
- Lines ≤100 characters. `ruff check` and `ruff format --check` must pass on `src` and `tests`.
- No abstraction without two real uses.
- Stdlib first. A new dependency needs user approval.
- Every behavior change has a test. Every bug fix has a test that fails before the fix.

## Skill authoring contract

Each `SKILL.md` must pass `engkit validate` (see `docs/skill-authoring.md`):

- Frontmatter has `name` (equal to the directory name) and `description` (≤1024 characters).
- At most 120 lines.
- Sections in this order: `When to use`, `When to ask`, `Objective`, `Inputs`, `Workflow`, `Output contract`, `Guardrails`, and optionally `References`.
- Outputs distinguish **verified fact**, **plausible hypothesis** and **untested assumption**.
- Memory hook: at task start, read `.engkit/memory/INDEX.md` if it exists, open only the entries that look relevant, and verify them against the code before relying on them. Do not write memory unless the skill's workflow says so.
- No skill implicitly authorizes edits, production access or destructive actions.
- Put depth in `references/` and load it only when relevant.
- Add trigger evals in `evals/triggers/` for each skill. Other cases live in `evals/` (see `evals/README.md`). Never let a test runner collect `evals/`.
