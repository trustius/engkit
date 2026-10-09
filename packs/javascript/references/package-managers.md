# JavaScript package-manager notes (optional pack reference)

- The lockfile identifies the package manager actually in use. Several lockfiles
  in one package are ambiguous: ask, or check CI and contributor docs, rather than
  picking one.
- `scripts.test` in `package.json` documents a test entry point; it is not
  evidence that the tests pass.
