# Plan: add truncate helper

> **Status:** Approved by the user.

## Slices

### Slice 1. Add `truncate`

- Create `src/textkit/truncate.py` with `truncate(text, limit)`; create `tests/test_truncate.py`.
- Verification: `python -m unittest tests.test_truncate` (cwd: project root).

### Slice 2. Show the limit in the README

- Edit `README.md` with one usage line.
- Verification: `python -m unittest discover -s tests` (cwd: project root).

## Acceptance criteria

- `python -m unittest discover -s tests` passes.
