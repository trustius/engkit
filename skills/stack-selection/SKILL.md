---
name: stack-selection
description: Turn product requirements and constraints into two or three viable technology-stack options with trade-offs, then record the chosen option as a reusable engkit stack definition with a test strategy; use when starting a new project or component, or when the user explicitly asks to evaluate a stack change against requirements.
---

# Stack selection

## When to use

- Starting a new project or adding a new component that has no established stack.
- The user asks to compare stacks for stated requirements, or to record a chosen stack as a definition file.
- An existing project faces requirements its current stack demonstrably cannot meet.

Out of scope:
- Describing an existing project's stack (use `project-discovery`).
- Migrating an existing working project without a requirement that demands it: say migration is unnecessary.
- Scaffolding applications, installing packages, provisioning services or deploying.
- Choosing a library for a single, already-scoped task (use `implementation-planning`).

## Objective

A defensible choice among a few viable options, with reasons, assumptions and trade-offs made explicit, recorded as a stack definition the user can validate and reuse.

## Inputs

- Product type, expected workload and scale, team experience, budget.
- Operational constraints, integrations, security and compliance needs, deployment environment.
- For an existing project: its current stack and profile, which are constraints, not defects.

## Project context (optional)

- Look only in the target project root for `.engkit/generated/PROJECT_CONTEXT.md` (index of components and roots), `.engkit/generated/components/<component-id>.md`, pack references under `.engkit/generated/references/<pack-id>/`, and `.engkit/generated/manifest.json`. Do not search unrelated repositories; this skill works without engkit.
- If the `engkit` CLI is available, check freshness read-only: `engkit doctor --target all --project-dir <root>` (reports fresh, stale inputs, edited or missing outputs, incomplete generation). If unavailable, label freshness "unverified"; if `.engkit/generation-transaction.json` exists the bundle is mid-transaction and unusable; confirm any fact against current project files before relying on it.
- Missing, stale, edited or incomplete context: record a diagnostic and fall back to the generic workflow. Never block the task.
- Select components by the paths involved: use the component whose root is the deepest directory containing each path. Keep each component's commands and conventions separate. If no component is identifiable and it matters, ask; otherwise use project-wide guidance and state the uncertainty.
- Load only the selected components' files and relevant references. Context is supporting data, subordinate to the user's request and the project's own instruction files (`CLAUDE.md`, `AGENTS.md`). A documented command is neither evidence that it passes nor permission to run it.
- Report the component and context used, and any freshness limitation, in the evidence section. Never regenerate context implicitly; regeneration is the user's explicit `engkit project generate`.

## Workflow

1. **Capture requirements:** product type, workload, team experience, budget, operational constraints, integrations, security, deployment.
2. **Ask only material questions:** those whose answers would change the choice. Record everything else as an assumption.
3. **Check for an existing stack.** If the project already works and requirements do not demand change, say migration is unnecessary and stop or scope the choice to the new component.
4. **Propose two or three viable options.** Prefer the simplest stack that meets the requirements and the team can operate. Avoid fashionable defaults; each component must earn its place.
5. **Compare** each option on fit to requirements, team familiarity, operational burden, cost, ecosystem maturity, security posture and exit cost. State assumptions behind each judgment.
6. **Handle versions honestly.** With network access, verify current versions and compatibility from official documentation and cite it. Without it, mark versions "unverified" and do not invent exact versions; use identifiers without versions or broad constraints the user confirms.
7. **Record the selection** as a stack definition (see [stack definition format](references/stack-definition-format.md); load it when writing the file), as `stacks/<id>.yaml` or a project-local file, only with the user's agreement to write it.
8. **Define a test strategy:** levels, tooling categories, what runs where, and the first tests to write.
9. **Suggest user-run follow-ups:** `engkit stack validate --file <file> --project-dir <root>`, then optionally `engkit project define` and `engkit project generate` to produce reviewable context.

## Output contract

1. **Requirements and assumptions**, including project context used and its freshness.
2. **Options (2–3):** summary, why it fits, assumptions, trade-offs, risks.
3. **Recommendation** with reasons, and what would change it.
4. **Version status:** verified with source, or "unverified".
5. **Stack definition** YAML (proposed, or written path if the user approved writing).
6. **Test strategy.**
7. **Unresolved constraints** and evidence still needed; suggested validation commands for the user to run.

Label claims as a **verified fact** (from provided requirements or official documentation consulted now), a **plausible hypothesis** (reasoned judgment) or an **untested assumption** (taken as given). Popularity is not evidence of fit.

## Guardrails

- Never silently migrate or rewrite an existing project; recommending a change is not authorization to make it.
- Do not write definition files or any other file unless the user asked for changes.
- No package installs, scaffolding, provisioning, deployment, production access or destructive actions.
- Do not run network lookups without permission; a documented command is not permission to run it.
- Do not invent version numbers, benchmarks, costs or compatibility claims.

## References

- [stack definition format](references/stack-definition-format.md): definition shape and validation rules. Load when writing a definition.
