# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - Unreleased

### Added

- Six skills: `systematic-debugging`, `change-review`, `implementation-planning`,
  `project-discovery`, `stack-selection` and `project-memory`.
- CLI commands: `list`, `validate`, `install` (built-in skills and `--source` git
  URLs, with a preview that requires `--yes`), `update`, `uninstall`, `doctor`,
  and `memory init` / `memory validate`.
- `.engkit/skills.lock.json` lockfile recording installed sources and content hashes.
- Safety properties: installs are staged and never overwrite existing files;
  skill files (including bundled scripts) are never executed; `update` and
  `uninstall` only touch installs whose files still match the lockfile.

[0.1.0]: https://github.com/trustius/engkit/releases/tag/v0.1.0
