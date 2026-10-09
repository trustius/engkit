# Eval result

Copy to `evals/<skill-dir>/<case-id>/results/<date>-<platform>-<condition>-<n>.md`.
Leave a field blank rather than guessing. Outcome stays `not-run` until a real session is graded.

- **Case id:**
- **Date (YYYY-MM-DD):**
- **Platform + version:** (e.g. Claude Code x.y.z / Codex CLI x.y.z)
- **Model (exact id/version):**
- **Condition:** baseline | skill
- **Skill installed (name, scope, engkit version/commit):** (skill condition only)
- **Fixture commit/hash:**
- **Run order:** (first / second; how randomised)
- **Transcript location:**
- **Grader:** (name or role)  **Blind grading:** yes | no

## Scores (0-2; `n/a` if the dimension does not apply)

| Dimension | Score | Justification (cite transcript) |
|---|---|---|
| Factual correctness | | |
| Evidence quality | | |
| False positives | | |
| Regression coverage | | |
| Unnecessary work | | |
| Constraint adherence (selection only) | | |
| Honest unknowns (selection only) | | |
| Suitability (selection only) | | |

## Critical findings

| Expected finding (from case.md) | Hit / missed | Evidence in transcript |
|---|---|---|
| | | |

## Hallucinations observed

- (list each disallowed hallucination or other invented fact seen, with transcript reference; "none observed" if none)

## Optional measured cost (only if measured from platform output)

- Tokens:
- Tool calls:
- Wall-clock time:

## Outcome

**Outcome:** not-run

(Set to `pass` or `fail` only after a real session has been run and graded against the case's pass threshold.)

## Notes

- Deviations from procedure, platform limitations, clarifying questions asked by the agent and the answer given.
