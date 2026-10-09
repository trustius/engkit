# ADR 0005: PyPI packaging, resource layout and release pipeline

- Status: accepted (2026-10-09)
- Date: 2026-10-09
- Supersedes: the distribution and resource-lookup parts of ADR 0001

## Context

ADR 0001 chose Python and a wheel as the release artifact, but its layout
(`skills/` at the repository root, `setup.py` copying it into
`engkit/_resources/`, and `resource_root()` with a checkout fallback) was
fragile: it depended on a custom build hook and on the source checkout for
development. engkit must be installable from PyPI with `pipx install engkit`,
must find its bundled skills regardless of the current directory, and must
be released without stored credentials.

## Decision

**Package-data layout.** Canonical skills live in `src/engkit/skills/<name>/`
and ship as setuptools package data:

```toml
[tool.setuptools]
package-dir = {"" = "src"}
packages = ["engkit", "engkit.skills"]

[tool.setuptools.package-data]
engkit = ["skills/**/*"]
```

The built-in skills directory is `catalog.builtin_skills_dir()`, which returns
`Path(__file__).parent / "skills"`. Lookup never depends on the current working
directory and needs no fallback to a checkout.

**Standard build.** The project uses the standard setuptools backend without a
custom build hook. `setup.py`, `MANIFEST.in`, the `build_py` hook and the
`_resources` copy are removed.

**Dynamic version.** `__version__` in `src/engkit/__init__.py` is the single
source of truth. `pyproject.toml` reads it with
`[tool.setuptools.dynamic] version = { attr = "engkit.__version__" }`.

**Python and platforms.** `requires-python = ">=3.11"`. CI runs Linux and macOS
on Python 3.11, 3.12 and 3.13. Windows is unsupported. The no-replace rename
(ADR 0002), symlink handling and POSIX permission behavior are not tested
there, so no Windows claim is made.

**Release pipeline** (`.github/workflows/release.yml`, triggered by a tag
`vX.Y.Z`):

1. `build` job: checks that the tag equals `__version__` by reading the file as
   text, without executing project code; builds the sdist and wheel; runs
   `twine check`; uploads the `dist` artifact.
2. `publish-testpypi` job: environment `testpypi`, `id-token: write`, publishes
   the artifact to TestPyPI through Trusted Publishing (OIDC).
3. `publish-pypi` job: environment `pypi` with a required reviewer, publishes
   the same artifact to PyPI after manual approval.

Trusted Publishing is used on both indexes, so no API token is stored in the
repository or in GitHub secrets. Publishing is never run by an agent; the owner
performs the release steps in `RELEASING.md`.

## Supply-chain controls

- Every GitHub Action is pinned to a full commit SHA.
- Workflow permissions are minimal: `contents: read` by default; `id-token: write`
  only on the publish jobs.
- No secrets. Authentication is Trusted Publishing (OIDC) only.
- The tag must equal `__version__`, so a tag cannot publish a different version.
- Build once, publish the same artifact to TestPyPI and PyPI. The PyPI job
  does not rebuild.
- The tagged commit must be on `main`; a tag ruleset limits who can create `v*`
  tags, and both environments only accept `v*` tags.
- PyPI deployments are gated by a required reviewer.
- The release build installs hash-locked tools (`requirements/release-build.txt`:
  build, setuptools, packaging, pyproject_hooks) and builds with `--no-isolation`,
  so no unpinned package runs where the artifact is produced. `twine check` runs
  in a separate job without publish rights.
- A sha256 digest of `dist/` is recorded by the build job and verified before
  `twine check` and before each publish step.
- Runtime dependency: PyYAML only. Dev tools are pinned in the `dev` extra
  (`ruff==0.16.10`, `build==1.6.1`, `twine==7.0.0`).
- Distribution test (`tests/test_distribution.py`) builds a wheel from the
  sdist, installs it into a clean virtual environment, and runs the CLI outside
  the checkout. It checks that every built-in `SKILL.md` file is present and that no
  tests, evals, docs or caches are shipped.

## Consequences

- Users install with `pipx install engkit` (Python 3.11+).
- The wheel contains only the package and its skills; the sdist contains the
  source needed to rebuild it.
- Releases require a reviewer's approval and are immutable on PyPI. A bad
  release is fixed by yanking it and publishing a new patch version (see
  `RELEASING.md`).
- Windows users cannot be supported until the no-replace rename, symlink and
  permission behavior are implemented and tested there. Adding Windows needs a
  new ADR.
- The `dev` extra is required for building and checking locally, so contributors
  need network access once to install it.
