# Tarnwick runtime — team notes (fictional, synthetic)

Tarnwick is our in-house runtime for small batch tools. It is installed on developer machines
by the platform team; there is no public download.

## Layout
- Each project has a `tarnwick.toml` at the root naming the entry module.
- Modules live in `mods/` with the extension `.tnw`.
- Test files live in `tests/` and are named `*_test.tnw`.

## Commands (documented)
- Type/syntax check: `tarnwick check .`
- Run tests: `tarnwick test tests/`
- Run: `tarnwick run . -- <args>`

## Known gaps
- No package manager: shared code is copied in by hand.
- No linter or formatter.
- Runtime version is whatever the platform team installed; `tarnwick --version` prints it.
