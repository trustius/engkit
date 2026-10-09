# engkit

engkit is a portable library of engineering-workflow skills (`SKILL.md`) for
**Claude Code** and **OpenAI Codex**, plus a small offline CLI to list,
validate, install and diagnose them. The CLI can also describe a project's
stack and generate context that the skills can read.

engkit is not an agent runtime, an MCP server or an LLM client. It sends
nothing over the network and never runs your project's scripts.

## Skills

| Skill | Use it when |
|---|---|
| `systematic-debugging` | A test fails, an error appears, behavior is wrong or intermittent |
| `code-review` | A diff, PR or patch needs review |
| `implementation-planning` | A feature, migration, refactor or significant fix needs a plan before code |
| `project-discovery` | You are mapping an unfamiliar or multi-component repository |
| `stack-selection` | You are choosing a stack for a new project or component |

Every skill separates **verified fact**, **plausible hypothesis** and
**untested assumption**. None authorizes edits, production access or
destructive actions. All five optionally read engkit-generated project
context and fall back to a generic workflow without it.

## Quickstart

Requirements: Python 3.10+ and PyYAML 6 (the only runtime dependency).

```bash
git clone <this repo> engkit && cd engkit
python3 -m venv .venv && .venv/bin/pip install -e .   # fetches PyYAML if missing (needs network)
.venv/bin/engkit list
.venv/bin/engkit validate

# install into a project (default scope: the project; --project-dir defaults to cwd)
.venv/bin/engkit install systematic-debugging --target claude --project-dir ~/code/my-app
.venv/bin/engkit install code-review --target codex --project-dir ~/code/my-app
# install for your user account (writes ~/.claude/skills and ~/.codex/skills)
.venv/bin/engkit install implementation-planning --target all --global

.venv/bin/engkit doctor --target all --project-dir ~/code/my-app
```

Offline setup with an interpreter that already has PyYAML:
`python3 -m venv --system-site-packages .venv && .venv/bin/pip install --no-index --no-deps --no-build-isolation -e .`
(see `docs/adr/0001-language-and-distribution.md`).

To build a wheel to share:
`python3 -m pip wheel . --no-deps --no-build-isolation -w dist`, then
`pipx install dist/engkit-0.1.0-py3-none-any.whl`.

| Target | Project scope | User scope (`--global`) |
|---|---|---|
| `claude` | `<project>/.claude/skills/<name>/` | `~/.claude/skills/<name>/` |
| `codex` | `<project>/.agents/skills/<name>/` | `~/.codex/skills/<name>/` |

Installation copies files. It never overwrites anything:

- A second identical install prints `already installed`.
- A modified copy produces `conflict` (exit 3) and is left untouched.
- `--target all` reports each platform separately.

To pick up a new canonical version, move your copy aside yourself, then
install again. A `--force` option is future work. Check
`docs/compatibility.md` for what is verified on each platform.

### Using a skill

- **Claude Code:** skills under `.claude/skills/` are discovered by
  description. You can also ask for one by name ("use the code-review skill
  on this diff").
- **Codex:** skills under `.agents/skills/` are listed to the agent. Ask for
  the skill by name.

To point agents at the skills from your own instruction file, add a line to
your `CLAUDE.md` or `AGENTS.md` yourself, for example: "For bugs, follow the
systematic-debugging skill." engkit never edits these files.

## Project context (optional)

```bash
engkit project inspect --project-dir .            # read-only detection report (add --json)
engkit stack validate --file stacks/custom.yaml --project-dir .
engkit project define --stack stacks/custom.yaml --project-dir .   # writes .engkit/project.yaml if absent
engkit project generate --project-dir . --dry-run
engkit project generate --project-dir . --target all
engkit project generate --project-dir . --target all --replace-generated   # after a verified backup
engkit project generate --project-dir . --recover-generated                # after an interrupted run
```

The output goes to `.engkit/generated/`:

- `PROJECT_CONTEXT.md`, an index of components;
- `components/<id>.md`, with per-component stack, rendered commands,
  conventions, pack guidance, evidence and unknowns;
- copies of pack references;
- optional `platform/claude.md` and `platform/codex.md` drafts for you to
  paste into your instruction files;
- `manifest.json`, with input and output hashes.

Output is byte-for-byte deterministic. Unchanged inputs are a no-op. Changed
inputs or hand edits are a conflict until you pass `--replace-generated`.

Monorepos and polyglot repositories get one component per detected root.
Unknown stacks get a generic component with their unknowns listed.
Project-local technology packs go in `.engkit/packs/<id>/pack.yaml`. They are
data only and need no install step.

Details: `docs/profiles.md` (profiles, merge rules, packs, workflows) and
`docs/regeneration.md` (conflicts, backups, recovery).

## Security model

- Fully offline: no network, telemetry or LLM calls.
- Never executes bundled skill scripts, project manifests or documented
  commands. Commands are stored as argv arrays and only rendered.
- Writes only to:
  - the requested skills directory;
  - `.engkit/project.yaml` (`project define`, only when absent);
  - `.engkit/generated/`, plus its lock, journal, `staging/` and `backups/`.
- Never modifies `CLAUDE.md`, `AGENTS.md`, IDE configs or git hooks.
- Rejects path traversal, symlinked managed directories and symlinks that
  escape the toolkit, a skill or a pack. Concurrency limitations are
  documented in `docs/adr/0002-installation-safety.md`.
- `doctor` and `project inspect` are read-only.

## Contributing

```bash
.venv/bin/python -m unittest discover -s tests -t .       # full suite (~7s, includes a wheel build)
.venv/bin/python -m unittest tests.test_installer          # one module
.venv/bin/python -m unittest tests.test_installer.InstallerTest.test_conflict_leaves_existing_untouched
ENGKIT_SKIP_DIST=1 .venv/bin/python -m unittest discover -s tests -t .   # skip the distribution test
engkit validate
```

- Tests create temporary project and home directories. They never touch your
  real `~/.claude` or `~/.codex`.
- New skills: follow `docs/skill-authoring.md` and add two or more synthetic
  eval cases (`evals/README.md`).
- Platform-specific behavior belongs only in `src/engkit/platforms.py`.
- Architecture decisions: `docs/adr/`.

## Limitations

- **No live agent checks yet.** Agent-level behavior (discovery, invocation
  and context use) has not been checked in a live Claude Code or Codex
  session. See `docs/manual-smoke-tests.md`; every row is pending.
- **No eval results.** No eval case has been run. Every outcome in
  `evals/README.md` is `not-run`.
- **Path mappings come from local evidence.** Install destinations were
  checked against the installed CLI binaries, not current official docs. The
  Codex user-scope path is an open question (`docs/compatibility.md`).
- **TOML on Python 3.10.** TOML key-based detection rules need Python 3.11+.
  On 3.10 only file presence is used.
- **No replacement or removal commands.** There is no `uninstall`, `update`
  or install `--force`. Replacing generated context (`--replace-generated`) is
  the only replacement operation.
- **Parent-directory race.** Installation does not protect against a hostile
  concurrent replacement of a parent directory (ADR 0002).
- **Example packs only.** The bundled packs are small synthetic examples, not
  a catalog of supported stacks.
- **Windows is untested.**

## Release checklist

- [ ] `python -m unittest discover -s tests -t .` passes (record the output in `docs/test-results.md`)
- [ ] `engkit validate` passes; `engkit list` shows all five skills
- [ ] Distribution test passed (wheel installed outside the checkout)
- [ ] `docs/compatibility.md` re-verified against current official docs; adapter updated if paths changed
- [ ] Manual smoke tests run, or explicitly left pending, in `docs/manual-smoke-tests.md`
- [ ] Eval status table updated with real outcomes only
- [ ] Version bumped in `pyproject.toml` and `src/engkit/__init__.py`

## License

MIT (see `LICENSE`).
