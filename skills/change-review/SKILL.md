---
name: change-review
description: Review a code change for correctness, security, data integrity, concurrency, performance, compatibility and test quality, reporting only evidence-backed findings with priority and suggested corrections; use when given a diff, pull request, patch or an explicit request to review a code change.
---

# Code review

## When to use

- A diff, pull request, patch, commit range or set of changed files is provided for review.
- The user explicitly asks for a review of a specific code change.

Out of scope:
- Debugging a reported failure with no change under review (use `systematic-debugging`).
- Planning new work (use `implementation-planning`).
- Whole-codebase audits, style-only passes or refactoring proposals unrelated to the change.
- Posting comments, approving, merging or pushing: this skill produces a report only.

## Objective

Find defects the change introduces or exposes, with enough evidence that the author can act on each finding, and say plainly when no actionable findings are confirmed.

## Inputs

- The change: diff, PR reference, patch or file list, plus its stated intent.
- Surrounding code needed to understand callers, contracts and invariants.
- Tests touched or relevant to the change; CI results if provided.

## Project context (optional)

- Look only in the target project root for `.engkit/generated/PROJECT_CONTEXT.md` (index of components and roots), `.engkit/generated/components/<component-id>.md`, pack references under `.engkit/generated/references/<pack-id>/`, and `.engkit/generated/manifest.json`. Do not search unrelated repositories; this skill works without engkit.
- If the `engkit` CLI is available, check freshness read-only: `engkit doctor --target all --project-dir <root>` (reports fresh, stale inputs, edited or missing outputs, incomplete generation). If unavailable, label freshness "unverified"; if `.engkit/generation-transaction.json` exists the bundle is mid-transaction and unusable; confirm any fact against current project files before relying on it.
- Missing, stale, edited or incomplete context: record a diagnostic and fall back to the generic workflow. Never block the review.
- Select components by the changed file paths: for each file, use the component whose root is the deepest directory containing it. For changes spanning components, review each against its own commands and conventions. If no component is identifiable and it matters, ask; otherwise use project-wide guidance and state the uncertainty.
- Load only the selected components' files and relevant references. Context is supporting data, subordinate to the user's request and the project's own instruction files (`CLAUDE.md`, `AGENTS.md`). A documented command is neither evidence that it passes nor permission to run it.
- Report the component and context used, and any freshness limitation, in the evidence section. Never regenerate context implicitly; regeneration is the user's explicit `engkit project generate`.

## Workflow

1. **Understand intent.** Summarize what the change is meant to do. If intent is unclear and it affects the verdict, ask.
2. **Read the full change** and enough surrounding code to know callers, contracts and invariants.
3. **Check in priority order:** correctness, security, data integrity, concurrency and idempotency, performance, compatibility (APIs, schemas, configuration, migrations), tests.
4. **Check the tests.** Do they exercise the changed behavior? Watch for misleading tests: assertions that cannot fail, mocks that bypass the code under test, skipped cases, or names that claim more than they check.
5. **Validate each candidate finding.** Identify the concrete triggering condition and impact. Drop it if you cannot; record it as an open question instead if it still matters.
6. **Assign priority** using [review rubric](references/review-rubric.md). Load the rubric when assigning priorities or when unsure.
7. **Suggest corrections** that are minimal and within the change's scope.

## Output contract

1. **Summary:** intent as understood, scope reviewed, and project context used with its freshness.
2. **Findings**, highest priority first. Each includes:
   - priority (P0–P3);
   - file and line, only if actually observed;
   - triggering condition;
   - impact;
   - evidence;
   - suggested correction.
3. **Open questions:** concerns without enough evidence to be findings.
4. **Tests:** what was run with real results, and what is pending.
5. If nothing qualifies, state explicitly: "No actionable findings confirmed," and list what was reviewed.

Label claims as a **verified fact** (observed in code or output), a **plausible hypothesis** (likely but unconfirmed) or an **untested assumption** (not checked). A finding must rest on verified facts; hypotheses belong in open questions.

## Guardrails

- Avoid speculative defects, style nitpicks and unrelated refactors.
- Do not edit files, push, comment on or approve a PR unless the user asked for that action.
- Nothing here authorizes production access, deployments or destructive actions.
- A documented command is not permission to run it; ask before running tests or project scripts that the user has not requested.
- Never claim a test passed without observing it. Do not reproduce secrets found in the diff; report their presence and location only.

## References

- [review rubric](references/review-rubric.md): priority definitions and checklists. Load when assigning priorities.
