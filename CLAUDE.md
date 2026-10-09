# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state and commands

M0–M6C are implemented (see `docs/test-results.md`). The toolkit is Python ≥3.10 with one runtime dependency, PyYAML (`docs/adr/0001-language-and-distribution.md`). It is not yet a git repository. Agent-level platform checks and eval runs are still pending.

```bash
# offline dev setup (local Python 3.10 already has PyYAML; the venv's own setuptools was removed so the system 80.9 builds wheels)
~/.pyenv/versions/3.10.12/bin/python3 -m venv --system-site-packages .venv
.venv/bin/pip install --no-index --no-deps --no-build-isolation -e .

.venv/bin/python -m unittest discover -s tests -t .              # full suite (includes a wheel build)
.venv/bin/python -m unittest tests.test_generation                # one module
.venv/bin/python -m unittest tests.test_installer.InstallerTest.test_conflict_leaves_existing_untouched   # one test
ENGKIT_SKIP_DIST=1 .venv/bin/python -m unittest discover -s tests -t .   # skip the distribution test
.venv/bin/engkit validate                                         # skill lint
python3 -m pip wheel . --no-deps --no-index --no-build-isolation -w dist # build (use an interpreter with setuptools>=70.1)
```

pytest also works and is limited to `tests/` via pyproject. Never let a test runner collect `evals/`: fixtures are inert data.

Layout: `src/engkit/` contains `cli`, `catalog`, `validator`, `platforms`, `installer`, `fsutil`, `resources`, `profiles`, `packs`, `detection`, `resolution`, `define`, `generation` and `doctor`. Resources live at the repo root (`skills/`, `packs/`, `schemas/`, `templates/`, `stacks/`) and are copied into `engkit/_resources/` at build time by `setup.py`. Design decisions are in `docs/adr/`.

Read `IMPLEMENTATION_PLAN.md` before starting any task. After a milestone-sized change, report the files changed, the commands run and their results, any unresolved risks, and the next tasks.

## What engkit is

engkit is a portable library of engineering-workflow skills (`SKILL.md`) plus an offline, local CLI for **Claude Code and OpenAI Codex**. The MVP includes `list`, `validate`, `install`, `doctor`, `project inspect`, `stack validate`, `project define` and `project generate`. It is not an agent runtime, an MCP integration or an LLM client.

Four concerns stay separate (§14.1):
1. **Core skills** (`skills/<name>/SKILL.md`): stack-neutral workflows. The MVP skills are `systematic-debugging`, `code-review` and `implementation-planning`, plus `project-discovery` and `stack-selection` in M6.
2. **Project profile** (`.engkit/project.yaml`, `stacks/<id>.yaml`): observed or declared components, commands and evidence. The schemas are versioned.
3. **Technology packs**: bundled `packs/` and project-local `.engkit/packs/<id>/pack.yaml`; optional, declarative and data-only. Duplicate IDs are errors, not overrides. Dependencies resolve locally by exact version; no executable plugins or network lookup.
4. **Platform adapters** (`platforms` module): the only place that maps `(platform, scope, root)` to destination paths.

Planned CLI modules: `cli` (thin arg parsing and output only), `catalog` (discovery and duplicate rejection), `validator` (no side effects), `installer`, `platforms`. M6 adds profiles, schemas, detection, packs, resolution and generation.

Install destinations: verify these against current official docs and record any differences in `docs/compatibility.md`.

| Scope | Claude Code | Codex |
|---|---|---|
| Project | `<project>/.claude/skills/<name>/` | `<project>/.agents/skills/<name>/` |
| User (`--global`) | `~/.claude/skills/<name>/` | `~/.codex/skills/<name>/` |

## Invariants (must not be violated)

- **Single canonical source:** `skills/<name>/` is authoritative. Never commit per-platform copies, and keep platform-specific behavior in adapters only.
- **Skill names** use lower-case ASCII letters, digits and hyphens, and must equal the directory name. Reject traversal, absolute paths, and symlinks that escape the toolkit root.
- **Install is copy-based, staged and atomic:** copy to a temp sibling, validate, then publish using the no-replace concurrency contract in §5. A preflight check followed by an unconditional rename is insufficient. An identical destination reports `already installed`; a differing one reports `conflict`; an active reservation may report retryable `busy`. Reject symlinked managed destination parents and clean only operation-owned staging. Never overwrite installed skills in the MVP (installation `--force` comes later).
- **Packaged resources are independent of cwd:** bundle skills, built-in packs, schemas, templates and shipped stack definitions. Test the non-editable built distribution from a separate project without source-checkout access, including custom-pack generation.
- **Default scope is project** (`--project-dir` or cwd). Global scope requires `--global`.
- **Never execute** scripts bundled in skills, or project manifests/commands during detection or generation. Commands in profiles are argv arrays that are only rendered.
- **Never auto-modify** existing `CLAUDE.md`, `AGENTS.md`, IDE configs or git hooks. Generated output goes to `.engkit/generated/` and must be byte-for-byte deterministic. Changed output conflicts by default. `project generate --replace-generated` explicitly replaces only that bundle after a verified backup; `--recover-generated` restores an interrupted transaction without generating new output. Backup, lock, staging and journal paths under `.engkit/` are the limited exceptions (§14.6). Preserve unrelated files; dry-run writes nothing. `doctor` is read-only and never accepts incomplete output as fresh.
- **Tests use temp home and project dirs only.** Never touch the real `~/.claude` or `~/.codex`.
- **Use a real YAML parser** (small, pinned dependency if needed). Do not hand-roll YAML parsing. Otherwise prefer the standard library.
- **No network, telemetry or package installs** without explicit permission.
- **Honest reporting:** do not claim a test passed unless it ran. When Claude Code or Codex cannot be run locally, mark end-to-end checks as pending. Evals must never contain invented scores, and fixtures must be synthetic.

## Skill authoring conventions

Every `SKILL.md` has `name` and `description` frontmatter and these sections: when to use (including out-of-scope cases), objective, inputs, workflow, output contract, guardrails. Keep the body short. Put deep material in `references/`, loaded only when relevant. Outputs must distinguish **verified fact**, **plausible hypothesis** and **untested assumption**. No skill may implicitly authorize edits, production access or destructive actions. Technology names belong only in optional examples, references or packs.

All five skills use the optional project-context hook in §6.1.1: locate context in the target project, check freshness when possible, select components by task paths, and load only relevant references. Missing/stale context falls back to generic workflows; when the CLI is unavailable, freshness stays unverified and facts must be checked against current files. Keep commands scoped per component and never interpret documented commands as execution permission. Do not implicitly regenerate context.

Final delivery includes at least ten synthetic evaluation cases (two per skill), distribution and recovery tests, and recorded platform/context-consumption smoke tests or explicit pending status when unavailable.
