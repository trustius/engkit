# Releasing engkit

Packaging decisions are in `docs/adr/0005-pypi-packaging.md`. Agents never
create repositories, push, tag, configure PyPI or upload. The owner runs every
step marked **owner**.

## One-time setup (owner)

1. Confirm the name `engkit` is free or yours at https://pypi.org/project/engkit/.
2. Push the repository to GitHub as `trustius/engkit`.
3. Enable two-factor authentication on PyPI and TestPyPI.
4. On PyPI and on TestPyPI, add a **pending trusted publisher**:
   - owner `trustius`, repository `engkit`, workflow `release.yml`;
   - environment `pypi` on PyPI, and `testpypi` on TestPyPI.
5. In GitHub, create the environments `testpypi` and `pypi`. On **both**, set
   deployment rules to "Selected branches and tags" with the tag pattern `v*`.
6. Add a required reviewer to `pypi`.
7. Add a tag ruleset for `refs/tags/v*` that lets only maintainers create,
   update or delete release tags.
8. Keep "Require approval for workflows from fork pull requests" enabled.

The release workflow also refuses a tag whose commit is not on `main`, builds
with hash-locked tools (`requirements/release-build.txt`), and verifies a
sha256 digest of `dist/` before every publish step.

No API tokens are stored anywhere. Publishing uses Trusted Publishing (OIDC).

## Each release

1. **Prepare on `main` with CI green.**
   - Release blocker until done once: run the Codex `--global` smoke test in
     `docs/manual-smoke-tests.md` and confirm Codex reads `~/.agents/skills`.
   - Move the items under `## [Unreleased]` in `CHANGELOG.md` to a new
     `## [X.Y.Z] - YYYY-MM-DD` section with today's date.
   - Bump `__version__` in `src/engkit/__init__.py`.
   - Commit through a pull request. Do not tag yet.

2. **Local check** (from a clean checkout of `main`):

   ```bash
   python3.11 -m venv .venv && .venv/bin/pip install -e ".[dev]"
   .venv/bin/python -m build && .venv/bin/twine check dist/* && .venv/bin/python -m unittest discover -s tests -t .
   ```

3. **owner:** tag the release commit and push the tag. This starts the release workflow.

   ```bash
   git tag vX.Y.Z && git push origin vX.Y.Z
   ```

4. **Watch the release workflow** in GitHub Actions. The `build` job checks that
   the tag equals `__version__`, builds and runs `twine check`. The
   `publish-testpypi` job then uploads to TestPyPI.

   Verify the TestPyPI build in a separate pipx home, so an existing
   installation is not replaced:

   ```bash
   export PIPX_HOME="$(mktemp -d)"
   pipx install --index-url https://test.pypi.org/simple/ \
     --pip-args="--extra-index-url https://pypi.org/simple" engkit
   engkit --version && engkit list
   pipx uninstall engkit   # then unset PIPX_HOME
   ```

5. **owner:** approve the `pypi` environment in the workflow run. The
   `publish-pypi` job uploads the same artifact that was tested on TestPyPI.

6. **Clean-machine smoke test** (a machine or account without the development checkout):

   ```bash
   pipx install engkit
   engkit --version
   TMP="$(mktemp -d)"
   engkit install change-review --target claude --project-dir "$TMP"
   engkit doctor --project-dir "$TMP"
   ```

7. **Record results.** Add the real outcomes (commands, versions, pass or fail,
   and anything pending) to `docs/test-results.md`. Then create a GitHub Release
   from the tag `vX.Y.Z`, with the notes copied from the `CHANGELOG.md` section.

## Updating the release build tools

`requirements/release-build.txt` pins `build`, `setuptools` and their
dependencies with hashes. To update one, change its version and replace the
hash with the sha256 of the wheel published on PyPI
(`pip download --no-deps --only-binary=:all: --python-version 3.13 <pkg>==<version>`
then `shasum -a 256`). Keep `build` in the `dev` extra at the same version.

## If something goes wrong

- A re-run of a partly failed release is safe: the TestPyPI step skips files
  that already exist.
- **Wrong version or a broken build on TestPyPI:** this is harmless. Fix the
  problem, bump the version, and release again. TestPyPI also rejects a reused
  version number, so always bump.
- **Problem on PyPI:** uploads are immutable and a version number can never be
  reused. Yank the bad release on PyPI (it stays installable only with an exact
  pin), then release a new patch version with the fix. Record the yank and the
  reason in `CHANGELOG.md` and `docs/test-results.md`.
- **Tag pushed by mistake:** delete the tag only if the workflow has not
  published anything. If it has, treat it as a release and follow the PyPI
  item above.
