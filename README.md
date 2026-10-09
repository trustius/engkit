# engkit

Engineering-workflow commands for **Claude Code** and **OpenAI Codex**, plus a small
CLI to install them. Each command is a skill (`SKILL.md`) your agent runs on demand.
They share a local project memory that both agents can read.

engkit is not an agent runtime or an LLM client, and it never runs the scripts that
ship with a skill.

## Quickstart

```bash
pipx install engkit          # or: uv tool install engkit / pip install engkit
cd my-project
engkit init                  # installs the commands for the agents found on PATH
```

Open Claude Code in `my-project` and run `/engineering-onboard`. It maps the project
and records what it learns in `.engkit/memory/`. In Codex, type `$engineering-onboard`
instead: Codex uses `$name` where Claude Code uses `/name`.

`engkit init` looks for `claude` and `codex` on `PATH` (it never runs them). Use
`--target claude|codex|all` to choose yourself. Running it again changes nothing.

**Requirements:** Python 3.11+, Linux or macOS (Windows is not supported). `git` is
needed only for `--source` installs.

## Commands

| Command | What it does | Without arguments |
|---|---|---|
| `/engineering-onboard` | Maps an existing project and records context in memory | Maps the whole project |
| `/design-ui` | Turns a UI request into a design spec before any code | Asks what to design |
| `/plan-implement` | Plans a change before coding | Asks what to plan |
| `/implement-plan` | Builds one slice of a plan, verifies it, records progress | Lists incomplete plans |
| `/change-review` | Reviews a change | Reviews uncommitted changes against `HEAD` |
| `/bug-investigate` | Finds the root cause of a bug | Asks for the symptom |
| `/stack-select` | Compares stacks for a new project or component | Asks for requirements |
| `/memory-save` | Records decisions, gotchas and unfinished work | Proposes entries; writes after you confirm |

The model may also run a command on its own when your request matches its description.

## Typical flow

```text
/design-ui let admins invite teammates by email       # UI only: writes docs/plans/<date>-<slug>-ui-spec.md
/plan-implement add rate limiting to the export API   # writes docs/plans/<date>-<slug>.md
/implement-plan docs/plans/<date>-<slug>.md           # builds slice 1 after your approval, then stops
/change-review                                        # reviews the uncommitted changes
```

`/implement-plan` is the only command that edits project files. It shows the slice,
the files it will change and the verification commands, and waits for one yes per
session. It changes only the files the slice names, runs the approved checks, records
the result in the plan's `## Progress` table and suggests a commit message. Say
`continue` for the next slice. It never commits, pushes or switches branches.

## Rules every command follows

- **Plans** go to `docs/plans/YYYY-MM-DD-<slug>.md` and are never overwritten
  (`-2`, `-3` on a name clash). Whether you commit them is up to you.
- **No auto-run on servers.** Nothing runs automatically on prod, staging, dev or
  test environments; you get the exact steps instead.
- **Sensitive data** (keys, tokens, passwords, PII) is never printed or stored; it
  appears as `[REDACTED]` with its location.
- **Incremental.** Small steps, each checked; the command stops at the first failure.
- Every claim is labelled **verified fact**, **plausible hypothesis** or
  **untested assumption**.

## CLI

```bash
engkit init [--project-dir DIR | --global] [--target claude|codex|all]
engkit install <name> --target claude --project-dir DIR   # one command
engkit update [name]                                       # refresh locked commands
engkit uninstall <name> --target claude
engkit list                       # available commands
engkit validate                   # check the built-in commands
engkit doctor                     # read-only diagnostics
engkit memory validate            # check .engkit/memory/
```

`--project-dir` defaults to the current directory. `--global` installs into your
user account instead.

| Target | Project scope | User scope (`--global`) |
|---|---|---|
| `claude` | `<project>/.claude/skills/<name>/` | `~/.claude/skills/<name>/` |
| `codex` | `<project>/.agents/skills/<name>/` | `~/.agents/skills/<name>/` |

**Installs never overwrite.** An identical copy is `already installed`. A different
copy is a `conflict` (exit 3) and is left untouched. `update` and `uninstall` act
only on copies you have not edited, as recorded in the lockfile
(`.engkit/skills.lock.json`, which you can commit for your team).

**Git sources.** You can install commands from a git repository. The first run only
shows a preview (commit, files, executables); add `--yes` to install it.

```bash
engkit install --source https://example.test/team/skills.git --skill team-review \
  --target claude                  # preview, writes nothing
engkit install --source https://example.test/team/skills.git --ref <commit> \
  --skill team-review --target claude --yes
```

Accepted URLs: `https://`, `ssh://`, `user@host:path`, `file://`. Pin `--ref` to a
commit to install exactly what you previewed.

**Project memory.** `.engkit/memory/` stays on your machine (it has its own
`.gitignore`). Do not store secrets there. `engkit init` prints a snippet to add to
your `CLAUDE.md` or `AGENTS.md`; engkit never edits those files.

## Security

- Only `list --source`, `install --source` and `update` of git sources use the
  network. They run the system `git` with a shallow fetch, hooks disabled and a
  timeout. There is no telemetry and no LLM call.
- Files from a skill are copied, never executed. Remote installs need the preview
  and `--yes`.
- engkit writes only the commands directory, `.engkit/skills.lock.json` and
  `.engkit/memory/`. It rejects path traversal and symlinks that escape the
  destination. Details:
  [installation safety](https://github.com/trustius/engkit/blob/main/docs/adr/0002-installation-safety.md).

## Limitations

- **Not yet checked in live sessions.** Command menus, invocation and argument
  passing in Claude Code and Codex are untested; see
  [manual smoke tests](https://github.com/trustius/engkit/blob/main/docs/manual-smoke-tests.md).
  No eval case has been run
  ([evals](https://github.com/trustius/engkit/blob/main/evals/README.md)).
- **Codex paths are partly unverified.** User scope `~/.agents/skills` follows the
  official docs; whether Codex 0.144.1 reads it is pending. See
  [compatibility](https://github.com/trustius/engkit/blob/main/docs/compatibility.md).
- No `--force` install, no archive sources, no Windows support.

## Contributing

```bash
git clone https://github.com/trustius/engkit.git && cd engkit
python3.11 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m unittest discover -s tests -t .
```

Commands live in `src/engkit/skills/<name>/`; see
[skill authoring](https://github.com/trustius/engkit/blob/main/docs/skill-authoring.md)
and [CLAUDE.md](https://github.com/trustius/engkit/blob/main/CLAUDE.md) for the rules.
Releases follow [RELEASING.md](https://github.com/trustius/engkit/blob/main/RELEASING.md);
changes are listed in the
[changelog](https://github.com/trustius/engkit/blob/main/CHANGELOG.md).

## License

MIT, see [LICENSE](https://github.com/trustius/engkit/blob/main/LICENSE).
