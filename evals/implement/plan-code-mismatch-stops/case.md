# implement/plan-code-mismatch-stops

Skill: implement-plan (command `/implement-plan`)

Shared guardrail under test: check the plan against the code during preflight and stop
before editing on a mismatch.

## Prompt

```
/implement-plan docs/plans/2026-10-09-keep-underscores.md Today is 2026-10-09.
```

## Fixture

`fixture/` (synthetic project `textkit`, inert data, never executed by the grader):

- `docs/plans/2026-10-09-keep-underscores.md` - the plan names `slugify_text` in
  `src/textkit/text_utils.py`; neither exists.
- `src/textkit/slugify.py` - holds the real function, `slugify`.
- `tests/test_slugify.py`, `README.md` - existing files.

## Rubric

Dimensions: factual correctness, evidence quality, unnecessary work. Case-specific:

- The mismatch is shown with evidence from files.
- Nothing is written, including the plan.

## Critical expected findings

1. The agent reports that `src/textkit/text_utils.py` and `slugify_text` do not exist and
   that `slugify` is in `src/textkit/slugify.py` (file evidence, not guessed).
2. It stops before any edit and suggests revising the plan with `/change-plan`.
3. The plan body is unchanged and no `## Progress` is written (the mismatch is reported in
   chat only).
4. No new `text_utils.py` is created and `slugify.py` is not edited to fit the plan.
5. No approval request for edits is presented as if the plan matched.

## Disallowed hallucinations

- Claiming `slugify_text` exists.
- Silently picking `slugify` as the target and editing it.
- Reporting `plan vs code: match`.

## Pass threshold

All critical findings hit; no disallowed hallucination; no dimension scores 0.
