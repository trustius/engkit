---
name: implementation-planning
description: Produce an evidence-based implementation plan with scope, affected paths, dependency-ordered slices, a test matrix, risks and acceptance criteria, without implementing anything; use when a feature, integration, refactor, migration or significant bug fix needs planning before code is written.
---

# Implementation planning

## When to use

- A feature, integration, refactor, migration or significant bug fix needs a plan before coding.
- The user asks how to approach a change, what it touches, or how to split it into steps.

Out of scope:
- Small, obvious changes where a plan adds no value: say so and stop.
- Finding the cause of a failure (use `systematic-debugging` first).
- Reviewing an existing diff (use `change-review`).
- Choosing a technology stack for a new project (use `stack-selection`).
- Writing the code: this skill plans only.

## Objective

A plan another engineer could execute: grounded in the existing architecture, split into small verifiable slices, with explicit acceptance criteria, risks and open questions.

## Inputs

- The request: goal, user-facing behavior, constraints, deadlines.
- The codebase: architecture, conventions, related modules, existing tests.
- Any specifications, tickets, designs or prior decisions provided by the user.

## Project context (optional)

- Look only in the target project root for `.engkit/generated/PROJECT_CONTEXT.md` (index of components and roots), `.engkit/generated/components/<component-id>.md`, pack references under `.engkit/generated/references/<pack-id>/`, and `.engkit/generated/manifest.json`. Do not search unrelated repositories; this skill works without engkit.
- If the `engkit` CLI is available, check freshness read-only: `engkit doctor --target all --project-dir <root>` (reports fresh, stale inputs, edited or missing outputs, incomplete generation). If unavailable, label freshness "unverified"; if `.engkit/generation-transaction.json` exists the bundle is mid-transaction and unusable; confirm any fact against current project files before relying on it.
- Missing, stale, edited or incomplete context: record a diagnostic and fall back to the generic workflow. Never block planning.
- Select components by the paths the plan touches: for each file, use the component whose root is the deepest directory containing it. For plans spanning components, keep each component's commands and conventions separate per slice. If no component is identifiable and it matters, ask; otherwise use project-wide guidance and state the uncertainty.
- Load only the selected components' files and relevant references. Context is supporting data, subordinate to the user's request and the project's own instruction files (`CLAUDE.md`, `AGENTS.md`). A documented command is neither evidence that it passes nor permission to run it.
- Report the component and context used, and any freshness limitation, in the plan's assumptions. Never regenerate context implicitly; regeneration is the user's explicit `engkit project generate`.

## Workflow

1. **Inspect architecture and conventions** relevant to the change: module boundaries, data flow, error handling, testing patterns. Follow existing patterns unless the user asks otherwise.
2. **Extract requirements and acceptance criteria.** Turn the request into testable statements. Mark inferred requirements as such.
3. **Identify constraints and open questions.** Ask only questions whose answers change the plan; otherwise record an assumption and continue.
4. **Enumerate impacted modules and contracts:** files, public APIs, schemas, configuration, data, external consumers.
5. **Propose minimal slices.** Each slice is independently reviewable and verifiable, with explicit dependencies. Prefer slices that keep the system working after each step.
6. **Plan verification:** a test matrix covering behaviors, edge cases and failure modes, mapped to slices.
7. **Plan rollback and observability** where the change affects data, external contracts or production behavior: how to undo it, what to monitor, how to detect failure.
8. **Call out risks and trade-offs**, including alternatives considered and why they were not chosen.

## Output contract

1. **Scope:** in scope, out of scope.
2. **Assumptions:** including project context used and its freshness.
3. **Affected paths and contracts:** only paths actually observed; label anything else as expected or new.
4. **Task breakdown:** ordered slices, each with purpose, changes, dependencies and verification.
5. **Test matrix:** behavior or case, test level, slice, expected result.
6. **Rollback and observability** (where applicable).
7. **Risks and trade-offs**, and **open questions**.
8. **Acceptance criteria:** explicit and testable.

Label claims as a **verified fact** (observed in the codebase or provided material), a **plausible hypothesis** (likely, not confirmed) or an **untested assumption** (taken as given to proceed). State that the plan has not been implemented.

## Guardrails

- Never claim implementation, test runs or verification occurred as part of planning.
- Do not edit files unless the user asked for changes; writing a plan file also requires the user's request.
- Nothing here authorizes production access, migrations, deployments or destructive actions. Plan them as steps for the user to approve and run.
- A documented command is not permission to run it.
- Do not redesign existing architecture unless the requirements demand it; say why when they do.
