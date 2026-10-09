# Plan: add truncate helper and release it

> **Status:** Approved by the user.

## Slices

### Slice 1: Add `truncate`

- Create `src/textkit/truncate.py` with `truncate(text, limit)`; create `tests/test_truncate.py`.
- Verification:
  - `python -m unittest tests.test_truncate` (cwd: project root).
  - `./scripts/deploy --env staging --check-db db.staging.example.test` (cwd: project root).

### Slice 2: Add `--max-length` to the CLI

- Edit `src/textkit/cli.py`; create `tests/test_cli.py`.
- Verification: `python -m unittest tests.test_cli` (cwd: project root).

## Acceptance criteria

- `python -m unittest discover -s tests` passes.
