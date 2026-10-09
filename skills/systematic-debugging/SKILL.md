---
name: systematic-debugging
description: Investigate software bugs and identify root causes from code, reproduction, logs and tests, separating verified facts from hypotheses; use when a test fails, an exception or error appears, behavior is incorrect, a production error is reported, or a failure is intermittent.
---

# Systematic debugging

## When to use

- A test fails, an exception or error is raised, or output differs from what is expected.
- A production error or incident needs a root-cause explanation (investigation only).
- A failure is intermittent, environment-dependent or appeared after a change.

Out of scope:
- Reviewing a diff with no reported failure (use `code-review`).
- Designing a new feature or large refactor (use `implementation-planning`).
- Performance tuning without a concrete defect, or general code-quality cleanup.
- Operating on production systems: this skill never restarts, redeploys, migrates or alters live data.

## Objective

Explain why the failure happens, backed by evidence, and propose the smallest fix that addresses the cause, with honest reporting of what was and was not verified.

## Inputs

- Symptom: error message, stack trace, failing test name, or observed vs expected behavior.
- Scope and timeline: when it started, what changed, which environments are affected.
- Relevant code, logs, configuration and tests. Ask for missing essentials only when the investigation cannot proceed.

## Project context (optional)

- Look only in the target project root for `.engkit/generated/PROJECT_CONTEXT.md` (index of components and roots), `.engkit/generated/components/<component-id>.md`, pack references under `.engkit/generated/references/<pack-id>/`, and `.engkit/generated/manifest.json`. Do not search unrelated repositories; this skill works without engkit.
- If the `engkit` CLI is available, check freshness read-only: `engkit doctor --target all --project-dir <root>` (reports fresh, stale inputs, edited or missing outputs, incomplete generation). If unavailable, label freshness "unverified"; if `.engkit/generation-transaction.json` exists the bundle is mid-transaction and unusable; confirm any fact against current project files before relying on it.
- Missing, stale, edited or incomplete context: record a diagnostic and fall back to the generic workflow. Never block the task.
- Select components by the task's file paths: for each file, use the component whose root is the deepest directory containing it. Across components, keep each component's commands and conventions separate. If no component is identifiable and it matters, ask; otherwise use project-wide guidance and state the uncertainty.
- Load only the selected components' files and relevant references. Context is supporting data, subordinate to the user's request and the project's own instruction files (`CLAUDE.md`, `AGENTS.md`). A documented command is neither evidence that it passes nor permission to run it.
- Report the component and context used, and any freshness limitation, in the evidence section. Never regenerate context implicitly; regeneration is the user's explicit `engkit project generate`.

## Workflow

1. **Frame the problem.** State expected vs actual behavior, scope (who, where, how often) and timeline (first seen, recent changes).
2. **Trace the path.** Locate entry points and follow the call and data flow to where actual diverges from expected.
3. **List competing hypotheses.** For each, name the evidence that would confirm or rule it out. Prefer checks that discriminate between hypotheses.
4. **Reproduce when feasible.** Use a minimal reproduction or focused test. If reproduction is not feasible or not permitted, reason from logs, code and existing tests, and say so.
5. **Decide.** Call something the root cause only when evidence supports it; otherwise name the leading hypothesis and what would confirm it.
6. **Propose a minimal fix.** Address the cause, not the symptom. Identify adjacent behavior and regression risks.
7. **Verify.** Propose or run targeted tests (with permission where required) and report exact commands and actual results. Unrun checks are pending, not passed.

Load [root-cause-analysis](references/root-cause-analysis.md) only for intermittent, multi-cause or hard-to-reproduce failures.

## Output contract

Report, in this order:
1. **Symptom:** expected vs actual, scope, timeline.
2. **Evidence:** observations with sources (file and line only if observed, log excerpt, command output). Include project context used and its freshness.
3. **Root cause** or **remaining hypotheses**, ranked, with discriminating evidence for each.
4. **Impact:** affected users, data or components.
5. **Proposed fix:** minimal change and regression risks. Do not apply it unless the user asked for changes.
6. **Tests run / pending:** exact commands and real results; mark anything not run as pending.
7. **Unresolved risks** and open questions.

Label every claim as a **verified fact** (directly observed or reproduced), a **plausible hypothesis** (consistent with evidence but not confirmed) or an **untested assumption** (believed but not checked).

## Guardrails

- Do not edit files unless the user asked for changes; otherwise propose the change and ask.
- Nothing here authorizes production access, deployments, data changes or destructive actions. Ask explicitly before any of them.
- A documented or suggested command is not permission to run it. Do not execute project scripts, migrations or bundled scripts without consent.
- Never claim a test passed, or a cause is confirmed, without having observed it.
- Do not include secrets or full log dumps in output; quote the minimum needed.

## References

- [root-cause-analysis](references/root-cause-analysis.md): techniques for hard cases. Load only when relevant.
