# Metrics

## Baseline (commit ca79005, 2026-10-09)

Tests: 131 passing (`python -m unittest discover -s tests -t .`).

| Module | Lines |
|---|---|
| `__init__.py` | 3 |
| `__main__.py` | 5 |
| `catalog.py` | 140 |
| `cli.py` | 291 |
| `define.py` | 112 |
| `detection.py` | 261 |
| `doctor.py` | 108 |
| `errors.py` | 16 |
| `fsutil.py` | 249 |
| `generation.py` | 762 |
| `installer.py` | 215 |
| `packs.py` | 385 |
| `platforms.py` | 64 |
| `profiles.py` | 492 |
| `resolution.py` | 273 |
| `resources.py` | 38 |
| `validator.py` | 148 |
| **total** | 3562 |

Skill names below are as of this date; they were later renamed (project-discovery→engineering-onboard, implementation-planning→plan-implement, systematic-debugging→bug-investigate, stack-selection→stack-select, project-memory→memory-save, code-review→change-review).

| SKILL.md | Lines |
|---|---|
| `code-review` | 74 |
| `implementation-planning` | 69 |
| `project-discovery` | 72 |
| `stack-selection` | 73 |
| `systematic-debugging` | 74 |

## After enhancement plan P0–P6 (2026-10-09)

Tests: 173 passing, 0 skipped (`python -m unittest discover -s tests -t .`). ruff check and format clean.

| Module | Lines |
|---|---|
| `__init__.py` | 3 |
| `__main__.py` | 5 |
| `catalog.py` | 149 |
| `cli.py` | 319 |
| `doctor.py` | 128 |
| `errors.py` | 16 |
| `fsutil.py` | 251 |
| `installer.py` | 674 |
| `lockfile.py` | 124 |
| `memory.py` | 203 |
| `platforms.py` | 96 |
| `resources.py` | 36 |
| `sources.py` | 190 |
| `validator.py` | 219 |
| **total** | 2413 (plan target ≤1800: not met) |

Skill names below are as of this date; they were later renamed (project-discovery→engineering-onboard, implementation-planning→plan-implement, systematic-debugging→bug-investigate, stack-selection→stack-select, project-memory→memory-save, code-review→change-review).

| SKILL.md | Lines |
|---|---|
| `change-review` | 76 |
| `implementation-planning` | 79 |
| `project-discovery` | 77 |
| `project-memory` | 76 |
| `stack-selection` | 82 |
| `systematic-debugging` | 81 |
