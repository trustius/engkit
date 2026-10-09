---
name: bug-investigate
description: Investigate a software bug and find its root cause from code, reproduction, logs and tests, labelling each claim as verified fact, plausible hypothesis or untested assumption. Use when a test fails, an error or exception appears, behavior is wrong, a production error is reported, or a failure is intermittent.
---

# Systematic debugging

## When to use
- A test fails, an exception is raised, or output differs from what is expected.
- A production error needs a root-cause explanation (investigation only).
- A failure is intermittent, environment-dependent or appeared after a change.
- Out of scope: reviewing a diff with no failure (use `change-review`); designing a feature
  (use `change-plan`); tuning performance with no defect; cleanup; operating on
  production (restart, redeploy, migrate, alter data).

## When to ask
- No symptom, error text, failing test or expected behavior is given: ask for it.
- Reproduction needs credentials, production data, or running commands the user did not allow.
- Memory or documentation contradicts the current code: report both and ask which to trust.
- The fix would need a file edit and the user only asked for diagnosis.
- Two causes fit the evidence equally and one more observation would split them: ask for it.

## Objective
Explain why the failure happens with evidence, propose the smallest fix for the cause, and
report honestly what was and was not verified.

## Inputs
- Symptom: error message, stack trace, failing test, or observed vs expected behavior.
- Timeline: when it started, what changed, which environments are affected.
- Relevant code, logs, configuration and tests.
- Project memory (optional): if `.engkit/memory/INDEX.md` exists in the target project, read
  it and open only entries relevant to the task. Verify each against current code before
  relying on it, and report which entries were used. If absent, proceed normally. Write memory
  only if the user's task allows it, following the memory-save format.

## Workflow
1. Read the user's symptom and write expected vs actual behavior in one sentence each.
2. If memory exists, read INDEX.md and open entries that mention the failing area.
3. Read the entry point of the failing path, then follow calls and data to where actual
   behavior diverges from expected.
4. List at least two competing hypotheses. For each, name one observation that would confirm
   or rule it out.
5. If the user permitted running commands, run the smallest reproduction or focused test and
   record the exact command and result. Otherwise do not run anything; reason from code, logs
   and existing tests, and say so.
6. If one hypothesis is supported by an observation and the rest are ruled out, call it the
   root cause. Otherwise report the ranked hypotheses and the next discriminating check.
7. Write the smallest fix that addresses the cause, and list adjacent behavior it could break.
8. Name one test that fails before the fix and passes after. Mark it pending unless run.
9. If the failure is intermittent or multi-cause, read
   [root-cause analysis](references/root-cause-analysis.md) and apply it.

## Output contract
Fill in this template.

```
Symptom: <expected vs actual; scope; timeline>
Memory used: <entry - verified | stale | unverifiable> or none
Evidence:
- verified fact: <observation> (source: <file:line, log excerpt or command output>)
- plausible hypothesis: <claim> (would be confirmed by: <check>)
- untested assumption: <claim>
Root cause: <statement> or Remaining hypotheses: <ranked list>
Impact: <users, data, components>
Proposed fix: <minimal change; regression risks> (not applied)
Commands run: <exact command - result> or none
Commands not run (pending): <command - why>
Open questions: <list>
```

## Guardrails
- Do not edit files unless the user asked for changes; propose and ask.
- No production access, deployments, data changes or destructive actions without explicit
  permission.
- A documented or suggested command is not permission to run it. Do not execute project
  scripts or migrations without consent.
- Never claim a test passed or a cause is confirmed without observing it.
- Never record or quote secrets; quote the minimum log text needed.

## References
- [root-cause analysis](references/root-cause-analysis.md): techniques for hard cases.
