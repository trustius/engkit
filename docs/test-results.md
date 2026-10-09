# Recorded test results

## 2026-10-09: PyPI packaging R1–R3 (engkit 0.1.0, unreleased)

Environment: macOS (Darwin 25.5.0, arm64), Python 3.11.9 venv, PyYAML 6.0.3, setuptools 84.0.0,
build 1.6.1, twine 7.0.0, ruff 0.16.10, git 2.39.2.

| Command | Result |
|---|---|
| `.venv/bin/python -m build` (isolated build env, setuptools fetched from PyPI) | built `engkit-0.1.0.tar.gz` and `engkit-0.1.0-py3-none-any.whl`, no warnings |
| `.venv/bin/twine check dist/*` | both PASSED |
| `.venv/bin/python -m unittest tests.test_distribution` | 3 passed: wheel from sdist has all 6 `SKILL.md` and no tests/evals/docs/caches; `engkit --version` equals wheel metadata; installed CLI works from an unrelated directory |
| `.venv/bin/python -m unittest discover -s tests -t .` | **175 passed** |
| `.venv/bin/ruff check src tests`, `ruff format --check src tests` | clean |

Not run: CI on GitHub (no push yet), TestPyPI/PyPI upload, `pipx install engkit` on a clean machine.

## 2026-10-09: enhancement plan P0–P6 (engkit 0.1.0, unreleased)

Environment: macOS (Darwin 25.5.0, arm64), Python 3.10.12 venv, PyYAML 6.0.2, git 2.39.2,
ruff 0.16.10. No network: git tests use `file://` repositories in temp directories.

| Command | Result |
|---|---|
| `.venv/bin/python -m unittest discover -s tests -t .` | **173 tests passed**, 0 skipped |
| `.venv/bin/ruff check src tests` / `ruff format --check src tests` | clean |
| `.venv/bin/engkit validate` | `ok: 6 skill(s) valid` |
| README quickstart from a fresh clone (temp HOME, `file://` source) | ran end to end: list, validate, built-in installs, remote preview then `--yes`, update (preview, then `--yes`), uninstall, memory init/validate, doctor |

Not run: agent-level smoke tests (`manual-smoke-tests.md`), eval cases and trigger evals
(`evals/README.md`, `evals/triggers/README.md`): every outcome is `not-run`.

## Earlier: initial MVP

## 2026-10-09: initial MVP implementation (engkit 0.1.0)

Environment: macOS (Darwin 25.5.0, arm64), Python 3.10.12 venv
(`--system-site-packages`, PyYAML 6.0.2, setuptools 80.9.0), offline.

| Command | Result |
|---|---|
| `.venv/bin/python -m unittest discover -s tests -t . -v` | **124 tests, all passed** (about 6 s) |
| `.venv/bin/python -m pytest -q` | 124 passed (pytest 8.2.1; `testpaths = ["tests"]`) |
| `engkit validate` | `ok: 5 skill(s) valid` |
| `engkit list` | 5 skills listed |

Tests per module:

| Module | Tests | Covers |
|---|---|---|
| test_catalog | 9 | ordering, descriptions, empty or missing dirs, hidden entries, missing SKILL.md, duplicates, symlinked skill dirs, frontmatter errors |
| test_validator | 13 | invalid names, name/dir mismatch, missing or malformed frontmatter, description limits, sections, missing or escaping references, escaping symlinks, single-skill validation, canonical skills plus context-hook phrases |
| test_platforms | 2 | the four scope/platform destinations, target expansion |
| test_installer | 20 | project/global/all, nested copies, no script execution, idempotency, conflict preservation, failed copy cleanup, permission failure, symlinked parents and destinations, destination appearing before publication (native and reservation paths), busy reservation, concurrent identical and differing installers (threads, both paths) |
| test_profiles | 14 | schema versions, malformed input, contained paths, duplicate ids/roots/entries, version syntax, stack definitions, merge rules (scalar, map, list replacement, keyed components, evidence union), precedence, contradictions, provenance, unknown stack |
| test_packs | 10 | bundled validity, project-pack discovery plus dependency, duplicate ids naming both paths, exact-version mismatch, missing deps, cycles, conflicts, dependency ordering, invalid packs (paths, rules, templates, schema range, malformed), symlink escape |
| test_detection | 7 | JVM, Go, Rust, JS fixtures; monorepo components, scoped commands and lockfile ambiguity; skipped vendored dirs; unknown-stack fallback; custom pack; symlinks not followed; malformed manifests; read-only (snapshot unchanged); tripwire not executed |
| test_define | 6 | stack validate with or without the project registry, unsafe roots, define new / already defined / conflict / dry-run, contradictions on existing projects, manual definition of an unknown stack, shipped example stack |
| test_generation | 23 | manifest consistency, no absolute paths, scoped component context, deterministic bytes, no-op, profile-change and user-edit conflicts, replacement with verified backup, preserved unrecognized files, missing manifest, target change, dry-runs (create, replace, recover), invalid selection blocks writes, unknown stack, custom-pack generation, injected failures at 5 stages with rollback, backup failure, first-generation failure, interruption at 3 stages then blocked and recovered, recovery to absence, refusal of post-crash edits, tampered journal, concurrent generation (busy), stale lock not reclaimed, symlinked generated dir, freshness (new, removed, edited, missing) |
| test_cli | 12 | help, version, invalid args (exit 2), list/validate (incl. failure paths), install default cwd/conflict/global (temp HOME), project workflow end to end, stack validate registry context, read-only doctor, incomplete transaction error, CLAUDE.md/AGENTS.md unchanged |
| test_schemas | 3 | JSON Schema documents match the validator constants |
| test_evals | 4 | ≥10 cases, ≥2 per skill, required sections, status table only pass/fail/not-run, no executable fixtures |
| test_distribution | 1 | wheel built from a deleted source copy, installed into a fresh venv; `list`, `validate`, `install --target all`, `project generate` with a project-local pack and `doctor` from an unrelated cwd; skills directory reported under the venv's site-packages |

Not covered by automation, and pending: agent-level discovery, invocation and
context consumption on Claude Code and Codex (`manual-smoke-tests.md`), and
all eval runs (`evals/README.md`, every row `not-run`).
