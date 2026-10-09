# Plan: make slugify keep underscores

> **Status:** Approved by the user.

## Slices

### Slice 1. Keep underscores in `slugify_text`

- Edit `slugify_text` in `src/textkit/text_utils.py` so that `_` is kept.
- Add a case to `tests/test_slugify.py`.
- Verification: `python -m unittest tests.test_slugify` (cwd: project root).

### Slice 2. Document the rule

- Edit `README.md`.
- Verification: `python -m unittest discover -s tests` (cwd: project root).

## Acceptance criteria

- `slugify("a_b")` returns `a_b`.
