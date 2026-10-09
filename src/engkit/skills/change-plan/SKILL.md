---
name: change-plan
description: Produce an evidence-based implementation plan with scope, affected paths, dependency-ordered slices, a test matrix, risks and acceptance criteria, without implementing anything. Use when a feature, integration, refactor, migration or significant fix needs planning before code is written.
---

# Implementation planning

## When to use
- A feature, integration, refactor, migration or significant fix needs a plan before coding.
- The user asks how to approach a change, what it touches, or how to split it into steps.
- Out of scope: small obvious changes (say so and stop); finding a failure's cause (use
  `bug-investigate`); reviewing a diff (use `change-review`); choosing a stack for a new
  project (use `stack-select`); writing the code.

## When to ask
- The goal or an acceptance criterion is ambiguous and two readings give different plans.
- A requirement conflicts with existing code, documented constraints or memory entries.
- The plan involves production, data migration or destructive steps: confirm who runs them.
- A missing constraint (deadline, compatibility, rollout limits) would change slice order.
- The user may want the plan saved to a file: ask before writing it.

## Objective
A plan another engineer could execute: grounded in the existing architecture, split into small
verifiable slices, with testable acceptance criteria, risks and open questions.

## Inputs
- The request: goal, user-visible behavior, constraints, deadlines.
- The codebase: architecture, conventions, related modules, existing tests.
- Specifications, tickets or prior decisions the user provides.
- Project memory (optional): if `.engkit/memory/INDEX.md` exists in the target project, read
  it and open only entries relevant to the paths involved. Verify each against current code
  before relying on it, and report which entries were used. If absent, proceed normally. Write
  memory only if the user's task allows it, following the memory-save format.

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
```

## Guardrails
- Never claim implementation, test runs or verification happened during planning.
- No edits unless the user asked; writing a plan file also needs the user's request.
- No production access, migrations, deployments or destructive actions; plan them as steps
  for the user to approve and run. A documented command is not permission to run it.
- Do not redesign existing architecture unless requirements demand it; say why.
- Never record secrets in the plan or in memory.
