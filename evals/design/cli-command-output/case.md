# design/cli-command-output

Skill: design-ui (command `/design-ui`)

Behavior under test: a UI spec for terminal output uses terminal concepts only.

## Prompt

```
/design-ui add a status command that lists running jobs Today is 2026-10-09.
```

## Fixture

`fixture/` (synthetic project `jobq-example`, inert data, never executed by the grader):

- `src/jobq/cli.py` - plain-text help output and usage exit code.
- `src/jobq/store.py` - the job record fields.
- `docs/cli-style.md` - output and exit-code conventions.

## Rubric

Dimensions: factual correctness, evidence quality, false positives, unnecessary work.
Case-specific:

- Surface is identified as CLI, with conventions cited from `docs/cli-style.md`.
- The text wireframe is an output block, not a page layout.

## Critical expected findings

1. UI type is stated as CLI and the existing conventions are cited with their paths.
2. The spec handles terminal width (truncation or wrapping of long names) and a no-color mode.
3. A machine-readable output option (for example a JSON flag) is specified, marked as new.
4. Exit codes are specified, consistent with `docs/cli-style.md` (0 success, 2 usage).
5. Non-interactive use (piped output, no prompts) is covered; the empty state ("no running
   jobs") has its own wording in the copy table.
6. Only the spec file is written; `src/` is untouched and `jobq` is not run.

## Disallowed hallucinations

- Web concepts: hover, responsive pixel breakpoints, modals, buttons, focus rings.
- Claiming a `--json` flag or a status command already exists.
- Running `python -m jobq` or any project command.

## Pass threshold

All critical findings hit; no disallowed hallucination; no dimension scores 0.
