# Progress format

Load this when listing plans (no argument) or when writing or updating a plan's `## Progress`.
A plan is complete only if every slice has a `done` or `skipped` row (see the last section).

## Listing plans (no argument)
List only files in `docs/plans/` that contain `### Slice N: <title>` headings and whose
section is missing or incomplete. Exclude UI specs: names ending exactly `-ui-spec.md` or
`-ui-spec-<N>.md`. A plan without slices is not implementable; point to `/plan-implement`.

## Table
Append `## Progress` at the END of the plan if it is missing. Commands in the sample are synthetic examples. Use this table, one row per
slice, and update rows in place. Touch nothing else in the plan.

```
## Progress

| Slice | Status | Date | Verification | Notes |
|---|---|---|---|---|
| 1. Add limit config | done | 2026-10-09 | `pytest tests/test_limits.py` (example) -> pass | none |
| 2. Wire limiter into export | failed | 2026-10-09 | `pytest tests/test_export.py` (example) -> 1 failed | assertion on retry header; asked user |
```

## Rules
- Status values: `done`, `failed`, `blocked`, `skipped`. Use `skipped` only when the user says so.
- Record commands and results (pass, fail, counts), never their output and never any secret.
- Date is today's absolute date (YYYY-MM-DD); ask if it is unknown.
- A failed or blocked row is updated in place when the slice is retried.
- A slice whose manual check is still pending is `blocked` (Notes: manual check pending)
  until the user reports the result.

## Complete or incomplete
- Complete: every slice in the plan has a row that is `done` or `skipped`.
- Incomplete: the section is missing, a slice has no row, or any row is `failed` or `blocked`.
