---
name: change-plan
description: Produce an evidence-based implementation plan with scope, affected paths, dependency-ordered slices, a test matrix, risks and acceptance criteria, without implementing anything. Use when a feature, integration, refactor, migration or significant fix needs planning before code is written. Not for small obvious edits, for finding a failure's cause, or for reviewing existing code.
---

# /change-plan

## When to use
- The user runs `/change-plan <change>` (Codex: `$change-plan`) or asks how to approach a
  feature, integration, refactor, migration or significant fix before coding.
- The user asks what a change touches or how to split it into steps.
- Out of scope: small obvious changes (say so and stop); finding a failure's cause
  (`/bug-investigate`); reviewing a diff (`/change-review`); choosing a stack for a new
  project (`/stack-select`); writing the code.

## When to ask
- No argument and no change in the request: ask what change to plan before doing anything else.
- The goal or an acceptance criterion is ambiguous and two readings give different plans.
- A requirement conflicts with existing code, documented constraints or memory entries.
- The plan involves production, data migration or destructive steps: confirm who runs them.
- A missing constraint (deadline, compatibility, rollout limits) would change slice order.

## Objective
A plan another engineer could execute: grounded in the existing architecture, split into small
verifiable slices, with testable acceptance criteria, risks and open questions.

## Inputs
- Arguments: the text typed after the command (Claude Code passes it as `ARGUMENTS: ...`; when
  invoked automatically or in Codex, use the user's request) is the change to plan. With no
  argument, ask for it first.
- The codebase: architecture, conventions, related modules, existing tests.
- Specifications, tickets or prior decisions the user provides.
- Project memory (optional): if `.engkit/memory/INDEX.md` exists in the target project, read
  it and open only entries relevant to the paths involved. Verify each against current code
  before relying on it, and report which entries were used. If absent, proceed normally.

## Workflow
1. Restate the goal in one sentence and list the requirements as testable statements. Mark
   each as stated or inferred.
2. If memory exists, read INDEX.md and open entries about the affected areas.
3. Read the modules, tests and conventions the change touches. Follow existing patterns.
4. List affected files, public APIs, schemas, configuration and external consumers. Mark each
   as observed, expected or new.
5. List open questions. If an answer would change the plan, ask; otherwise record an
   assumption and continue.
6. Split the work into slices that are each reviewable and leave the system working. Give each
   a purpose, changes, dependencies and one verification.
7. Build a test matrix: behavior or edge case, test level, slice, expected result.
8. If the change touches data, external contracts or production, write rollback steps and what
   to monitor.
9. List risks, alternatives considered and why each was not chosen.
10. Write acceptance criteria. State that nothing was implemented.

## Output contract
Fill in this template.

```
Scope: in: <...>  out: <...>
Memory used: <entry - verified | stale | unverifiable> or none
Assumptions:
- verified fact: <observed in code or provided material>
- plausible hypothesis: <likely, not confirmed>
- untested assumption: <taken as given>
Affected paths: <path - observed | expected | new>
Slices: 1. <purpose; changes; depends on; verification>
Test matrix: <case | level | slice | expected>
Rollback and observability: <steps> or n/a
Risks and alternatives: <list>
Open questions: <list>
Acceptance criteria: <testable list>
Commands run: <exact command - result> or none
Status: plan only, not implemented
Next step: /change-review after the code is written, or none
```

## Guardrails
- Never claim implementation, test runs or verification happened during planning.
- Do not edit code or memory. Do not write a plan file unless the user asks.
- No production access, migrations, deployments or destructive actions; plan them as steps
  for the user to approve and run. A documented command is not permission to run it.
- Do not run project commands (build, test, scripts).
- Do not redesign existing architecture unless requirements demand it; say why.
- Never record secrets in the plan.
