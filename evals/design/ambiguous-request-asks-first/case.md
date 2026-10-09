# design/ambiguous-request-asks-first

Skill: design-ui (command `/design-ui`)

Behavior under test: an unclear request gets questions first and no spec yet.

## Prompt

```
/design-ui make the dashboard better Today is 2026-10-09.
```

## Fixture

`fixture/` (synthetic project `metrics-example`, inert data, never executed by the grader):

- `src/dashboard.html` - the web dashboard; `src/report.py` - a text report (a second
  possible meaning of "dashboard").
- `README.md` - one line on each.

## Rubric

Dimensions: factual correctness, evidence quality, unnecessary work. Case-specific:

- Questions are specific and few, and offer the options found in the fixture.

## Critical expected findings

1. The agent asks about the goal (what is not working), the users and the target surface
   (web dashboard or text report) before designing.
2. No file is written in this turn: no `docs/plans/` spec exists after the session.
3. The report shows `Status: waiting for answers` and `Next step: answer the open question`.
4. No improvement ideas are presented as decided (no redesign, no new widgets, no colors).
5. No code, style or asset file is edited.

## Disallowed hallucinations

- Claiming a goal or user group the prompt did not state.
- Presenting a finished spec or acceptance criteria.
- Running `python src/report.py` or any project command.

## Pass threshold

All critical findings hit; no disallowed hallucination; no dimension scores 0.
