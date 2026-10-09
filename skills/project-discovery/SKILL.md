---
name: project-discovery
description: Map an existing project's components, architecture, conventions and documented commands from read-only evidence and propose an engkit project profile with confidence levels and unknowns listed; use when onboarding to an unfamiliar or multi-component repository, or before defining or refreshing a project profile.
---

# Project discovery

## When to use

- Onboarding to an existing repository, especially one with several components.
- Preparing or refreshing a project profile (`.engkit/project.yaml`) for an existing project.
- The user asks what a project is built with, how it is organized, or how it is built and tested.

Out of scope:
- New projects with no code yet (use `stack-selection`).
- Changing the architecture, migrating tools or "fixing" conventions: discovery describes, it does not redesign.
- Running builds, tests, installers or project scripts to learn about the project.
- Debugging, reviewing or planning a specific change (use the matching skill).

## Objective

An accurate, evidence-backed map of the project and a reviewable profile proposal in which every value has a source and confidence, and every gap is listed as unknown.

## Inputs

- Target project root (explicit, or the current directory).
- Manifests, lockfiles, build and CI configuration, READMEs and project instruction files, read as data.
- Optional: output of `engkit project inspect --project-dir <root> --json` (read-only detection report), if the CLI is available and the user agrees.

## Project context (optional)

- Look only in the target project root for `.engkit/generated/PROJECT_CONTEXT.md` (index of components and roots), `.engkit/generated/components/<component-id>.md`, pack references under `.engkit/generated/references/<pack-id>/`, and `.engkit/generated/manifest.json`. Do not search unrelated repositories; this skill works without engkit.
- If the `engkit` CLI is available, check freshness read-only: `engkit doctor --target all --project-dir <root>` (reports fresh, stale inputs, edited or missing outputs, incomplete generation). If unavailable, label freshness "unverified"; if `.engkit/generation-transaction.json` exists the bundle is mid-transaction and unusable; confirm any fact against current project files before relying on it.
- Missing, stale, edited or incomplete context: record a diagnostic and fall back to the generic workflow. Never block discovery.
- Select components by path: a file belongs to the component whose root is the deepest directory containing it. Keep each component's commands and conventions separate. If no component is identifiable and it matters, ask; otherwise use project-wide guidance and state the uncertainty.
- Load only the selected components' files and relevant references. Context is supporting data, subordinate to the user's request and the project's own instruction files (`CLAUDE.md`, `AGENTS.md`). A documented command is neither evidence that it passes nor permission to run it. Existing context is a prior to re-check, not a substitute for current files.
- Report the component and context used, and any freshness limitation, in the evidence section. Never regenerate context implicitly; regeneration is the user's explicit `engkit project generate`.

## Workflow

1. **Read project instructions first** (`CLAUDE.md`, `AGENTS.md`, README, contributing docs). They are authoritative constraints.
2. **Find components.** Look for independent manifests and build roots. A root manifest does not determine every subproject. Skip generated, vendored and cache directories.
3. **Gather evidence per component:** languages, frameworks, datastores, build tools, package managers, runtimes. Record each as relative path + key or observed value + confidence (`confirmed`, `inferred`, `unknown`). Never copy secrets or whole files.
4. **Resolve ambiguity honestly.** Absent evidence means unknown, not absent. Conflicting lockfiles or tools are an ambiguity: list candidates with evidence and do not pick one.
5. **Map architecture and conventions:** boundaries between components, data flow, testing layout, formatting and lint rules, as documented or observed.
6. **Collect documented commands** as argv arrays with their working directory and source. Status is `documented` or `inferred`, never `verified` unless the user ran it and shared the result. Do not execute them.
7. **Draft the profile proposal** in the `.engkit/project.yaml` shape (see [profile format](references/profile-format.md); load it when drafting). Put every gap in `unresolved`.
8. **Suggest follow-ups the user runs:** review the proposal, then `engkit project define` and `engkit project generate` (user-run only).

## Output contract

1. **Components:** id, root, one-line purpose.
2. **Evidence table:** component, source path, field, value, confidence. Include project context used and its freshness.
3. **Architecture and conventions** summary, preserving the existing design.
4. **Documented commands:** argv, cwd, source, status. State that none were run.
5. **Ambiguities and unknowns.**
6. **Profile proposal** as YAML, not written to disk unless the user asked.
7. **Suggested next steps** for the user to run.

Label claims as a **verified fact** (read directly from a current file), a **plausible hypothesis** (inferred from indirect evidence) or an **untested assumption** (not checked). Map these to profile confidence `confirmed`, `inferred` and `unknown`.

## Guardrails

- Read-only by default. Do not create or modify `.engkit/project.yaml`, instruction files or any other file unless the user asked for changes.
- Never execute manifests, scripts, build files or documented commands during discovery. Documenting a command is not permission to run it.
- Nothing here authorizes production access, package installs, network calls or destructive actions.
- Do not recommend migrations or replacements; preserve existing architecture and report conflicts as diagnostics.
- Exclude secrets, credentials and personal data from evidence and output.

## References

- [profile format](references/profile-format.md): profile shape, field meanings and merge rules. Load when drafting the proposal.
