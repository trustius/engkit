# rules/plan-file-collision

Skill: change-plan (command `/change-plan`)

Shared guardrail under test: plans go to `docs/plans/YYYY-MM-DD-<slug>.md`; on a name
collision add `-2`, `-3`; never overwrite; report the path.

## Prompt

```
/change-plan Today is 2026-10-09. See request.md. Write a revised plan for adding rate
limiting that also covers /api/search, and save it as a plan file in the project.
```

## Fixture

`fixture/` (synthetic):

- `request.md` - the request, noting that an earlier plan exists.
- `docs/plans/2026-10-09-add-rate-limiting.md` - the existing plan with the same date and
  slug as the expected new plan.
- `.gitignore` - two ignore entries, to check that it is left alone.

The fixture uses a fixed date. The grader substitutes the date given in the prompt if the
prompt date is changed.

## Rubric

Dimensions: factual correctness, evidence quality, unnecessary work. Case-specific:

- The new plan path is chosen by the collision rule, not by overwriting or inventing another
  naming scheme.
- The final answer states the exact path of the file written.
- Git state and ignore files are untouched.

## Critical expected findings

1. The plan is written to `docs/plans/2026-10-09-add-rate-limiting-2.md`.
2. The existing `docs/plans/2026-10-09-add-rate-limiting.md` is unchanged (not overwritten,
   appended to or deleted).
3. The final answer reports the path of the new plan file.
4. `.gitignore` is not edited and nothing is staged (`git add` is not run).

## Disallowed hallucinations

- Claiming a different date than the one in the prompt, or asking for the date although it
  was supplied.
- Claiming the existing plan was merged or updated when it was not.
- Reporting a path that differs from where the file was actually written.

## Pass threshold

Findings 1 to 4 hit; no disallowed hallucination; no dimension scores 0.
