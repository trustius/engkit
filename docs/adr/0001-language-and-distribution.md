# ADR 0001: Implementation language, dependencies and distribution

- Status: accepted (M0)
- Date: 2026-10-09

## Context

engkit needs a small, cross-platform CLI that parses YAML, copies directory
trees safely and ships data resources (skills). The choice must not constrain the stacks of projects that
consume the skills; those projects never need engkit's language.

## Options considered

| Option | Distribution | Cross-platform FS primitives | YAML | Maintenance |
|---|---|---|---|---|
| Python (stdlib + PyYAML) | wheel / pipx; interpreter required | `os`, `ctypes` for no-replace rename | PyYAML (mature, `safe_load`) | Readable, easy to contribute to |
| Go | single static binary | `golang.org/x/sys` for renameat2 | `gopkg.in/yaml.v3` | Needs Go toolchain; binary per OS/arch |
| Node.js | npm package; runtime required | `fs` lacks no-replace rename (native addon) | `yaml` | Larger dependency trees |
| Rust | single binary | `rustix`/`nix` | `serde_yaml` (unmaintained upstream) | Slower contributor onboarding |

## Decision

Python, minimum **3.10**, packaged with setuptools as a wheel exposing the
`engkit` console script. Rationale: available on developer machines,
including this one, without new toolchains; the standard library covers
filesystem, JSON, hashing and argument parsing; `ctypes` gives access to the
OS no-replace rename primitives; PyYAML is the de facto safe YAML parser.

**Runtime dependency policy:** exactly one third-party runtime dependency,
`PyYAML>=6.0,<7`, used only through `yaml.safe_load` / `yaml.safe_dump`. No
other runtime dependencies without a new ADR. Tests use only `unittest`
(pytest also works but is not required).

**Network exception (ADR 0004):** `list --source`, `install --source` and
`update` of a git-sourced entry call the system `git`. All other commands stay
offline.

## Distribution and resource lookup

- The canonical source stays at the repository root: `skills/`. Nothing is
  duplicated in source control.
- `setup.py` subclasses `build_py` to copy `skills/` into `engkit/_resources/`
  inside the built package. The wheel is the release artifact.
- `engkit.resources.resource_root()` returns `<package>/_resources` when
  `skills/` exists there. Otherwise, for editable or `PYTHONPATH=src`
  development, it falls back to the checkout located relative to the module
  file (requires `pyproject.toml` next to `skills/`). **The current working
  directory is never consulted.** If neither location is found, the CLI fails
  with exit code 4.
- Project memory (`.engkit/memory/`) resolves against the explicit
  `--project-dir` (or cwd), never the resource root.

## Non-editable distribution smoke test

Automated in `tests/test_distribution.py`. It runs offline:

1. Copy the checkout to a temp directory and build a wheel from it with
   `pip wheel --no-deps --no-index --no-build-isolation`.
2. Delete the copied source.
3. Create a fresh venv. It reuses the interpreter's already-installed PyYAML via
   `--system-site-packages`, because no network installs are allowed. Install
   the wheel with `--no-index --no-deps`.
4. From an unrelated cwd, without `PYTHONPATH`, run `list`, `validate`,
   `install --target all`, `project generate` on a project with a
   project-local custom pack, and `doctor`. Assert that doctor reports
   `resources: bundled` under the venv path and never under the checkout.

Limitation: the original checkout still exists on disk during the test, so
"unavailable" is enforced by deleting the build source and asserting the
resource path, not by a sandbox.

## Consequences

- Users need Python 3.10+. `pipx install <wheel>` is the recommended
  isolated install.
- The development venv in this repo was created offline from a local Python
  3.10 that already had PyYAML 6.0.2 (`--system-site-packages`). The venv's
  bundled setuptools 65 was removed so the interpreter's setuptools 80.9
  (which builds wheels natively) is used.
