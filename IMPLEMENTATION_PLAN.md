# Engineering Skills Toolkit — Implementation Plan

> **Note (2026-10-09):** Sections on M6 (§14.x), generated project context and technology packs are superseded by `ENHANCEMENT_PLAN.md`. Those features were removed. Use `ENHANCEMENT_PLAN.md` as the current direction.

> **Audience:** Claude Code (implementation agent) and the engineer overseeing it  
> **Working name:** `engkit`  
> **Status:** Revised after design review; compatibility and runtime decisions remain M0 gates  
> **Implementation language:** Select during M0 based on distribution, portability, maintainability, and repository constraints; no mandatory language  
> **Targets:** Claude Code and OpenAI Codex

## 0. Agent operating instructions

Implement this plan incrementally in the current repository. First inspect the repository; do not overwrite existing work or assume an empty project. If files already exist, reconcile the plan with them and report discrepancies. Use standard, portable Agent Skills (`SKILL.md`) as the canonical format. Treat platform-specific capabilities as adapters, not as core dependencies.

**Execution rules:**
- Complete tasks in dependency order. For every task: inspect existing implementation, make the smallest coherent change, run relevant tests, and report evidence.
- Do not claim any test passed unless it actually ran. Do not fabricate platform compatibility. When Claude Code or Codex cannot be executed locally, mark end-to-end verification as pending.
- Do not install third-party packages, alter global user configuration, execute network-dependent commands, or overwrite project-specific instructions without permission.
- Never silently overwrite a user's installed skill. Implement conflict reporting and explicit replacement semantics.
- Keep skills short and operational. Put optional deep guidance under `references/`, rather than loading everything by default.
- Never include secrets, real production data, organization-specific private code, or proprietary incident details in example fixtures.
- After each milestone, summarize files changed, commands run, results, unresolved risks, and next tasks.

## 1. Product vision

Build an open, portable toolkit of **engineering workflows** usable by both Claude Code and Codex. The toolkit should improve software-engineering outcomes by making agents more systematic, evidence-driven, test-oriented, and conscious of correctness, security, performance, and regression risks.

This is **not** a new autonomous agent runtime or a replacement for Claude Code/Codex. The initial product consists of:
1. A curated library of portable `SKILL.md` workflows.
2. A small local CLI for listing, validating, installing, diagnosing, and eventually updating them.
3. Thin platform adapters and optional platform-specific instructions.
4. Reproducible test fixtures and evaluation rubrics.
5. A project-profile system that detects, defines, and generates stack-specific guidance through extensible technology packs.

**Guiding principle:** A skill describes **how to approach a task**, not just facts about a language or framework. Every investigation must distinguish **verified fact**, **plausible hypothesis**, and **untested assumption**.

## 2. Goals, non-goals, and success criteria

### Goals (MVP)
- A single canonical source for skills, without duplicated Claude/Codex copies in source control.
- Five portable skills: `systematic-debugging`, `code-review`, `implementation-planning` in M1, then `project-discovery` and `stack-selection` in M6C.
- Safe local project/global installation for Claude Code and Codex.
- `list`, `validate`, `install`, `doctor`, `project inspect`, `stack validate`, `project define`, and `project generate` CLI commands, with `--help` and actionable failures.
- Unit/integration tests with temporary directories; no changes to real user home directories during tests.
- Documentation for installation, invocation, authoring skills, and manual cross-platform verification.
- At least ten synthetic evaluation cases across the five MVP skills, with an explicit baseline comparison procedure.
- Stack discovery, custom stack definitions, deterministic project-context generation, and agent-guided stack selection for new projects.
- Multi-component profiles for monorepos and polyglot systems; generic fallback for unknown technologies.

### Non-goals (MVP)
- Building a general multi-agent orchestration framework.
- Automatically executing arbitrary scripts downloaded from skill packages.
- Remote registry, telemetry, cloud sync, LLM API integration, or automatic production access.
- MCP integration by default (design interfaces later only if needed).
- Automatic rewrites of existing `CLAUDE.md` or `AGENTS.md`.
- Mandatory execution of every engineering skill on every request.
- Automatically migrating existing projects to a preferred stack or scaffolding application code in the MVP.

### Definition of success
- A developer can clone the repo and install any MVP skill into a demo project for either supported platform.
- Installing for both targets produces valid, independently readable skill directories.
- Running installation twice is safe and produces an understandable no-op or conflict status; no silent data loss.
- Validation catches malformed metadata, missing required files, unsafe paths, and duplicate skill names.
- An installed distribution finds its bundled skills, packs, schemas and templates from a separate project without the source checkout.
- Existing, new, monorepo and unknown-stack projects can use profiles and local custom packs; generated context is consumed by the relevant skills.
- Context can be regenerated explicitly with a recoverable backup; conflicts and interrupted generation never masquerade as a fresh successful result.
- All automated tests pass; manual platform checks are documented separately and do not masquerade as automated verification.

The MVP includes M0–M5 followed by M6A → M6B → M6C. M5 is a core-toolkit checkpoint; final release readiness is assessed after M6C against section 13.

## 3. Compatibility model

Use portable Agent Skills frontmatter (`name`, `description`) and a `SKILL.md` body as the **source format**. Keep platform-specific extras out of shared metadata unless both platforms explicitly support them.

| Scope | Claude Code destination | Codex destination |
|---|---|---|
| Project | `<project>/.claude/skills/<name>/` | `<project>/.agents/skills/<name>/` |
| User | `~/.claude/skills/<name>/` | `~/.codex/skills/<name>/` |
| Project instructions | `CLAUDE.md` (opt-in) | `AGENTS.md` (opt-in) |

**Important:** Verify destination directories, discovery behavior, symlink support, naming limits, and invocation syntax against installed versions / current official docs during implementation. If a platform has different documented behavior, record it in `docs/compatibility.md` and adjust its adapter rather than polluting shared skills.

Prefer **copy-based installation** for the first release. Symlinks can be supported later as a development-only opt-in; copies are predictable across operating systems and sandboxes.

## 4. Architecture

```text
engkit/
├── skills/
│   ├── systematic-debugging/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── root-cause-analysis.md
│   ├── code-review/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── review-rubric.md
│   ├── implementation-planning/
│   │   └── SKILL.md
│   ├── project-discovery/        # M6C
│   │   └── SKILL.md
│   └── stack-selection/          # M6C
│       └── SKILL.md
├── packs/                       # optional declarative technology guidance
├── stacks/                      # reusable declarative stack definitions
├── schemas/                     # project profile, stack definition, pack contracts
├── templates/                   # portable project-context templates
├── src/engkit/                  # logical modules; adapt layout to selected language
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── catalog.py
│   ├── validator.py
│   ├── installer.py
│   └── platforms.py
├── tests/
│   ├── test_catalog.py
│   ├── test_validator.py
│   ├── test_installer.py
│   └── test_cli.py
├── evals/
│   ├── README.md
│   ├── debugging/
│   ├── review/
│   └── planning/
├── docs/
│   ├── compatibility.md
│   ├── skill-authoring.md
│   └── manual-smoke-tests.md
├── <package manifest>           # chosen implementation ecosystem
├── README.md
├── LICENSE
└── IMPLEMENTATION_PLAN.md
```

### Responsibilities
- **Catalog:** Discover canonical skill directories; load metadata; reject duplicates.
- **Validator:** Check metadata, files, naming, and references; no network or side effects.
- **Platform registry:** Map `(platform, scope, project_dir/home_dir)` to destinations, in one testable place.
- **Installer:** Copy validated skills safely; avoid collisions and partial installs; provide deterministic status.
- **CLI:** Parse arguments and present user-friendly output; keep core behavior importable and unit-testable.
- **Skills:** Product content; platform-neutral unless an exception is documented.
- **Evals:** Reusable prompts, expected findings, and scoring rubrics (not fabricated measurements).

### Distribution and resource lookup

The release artifact must include canonical `skills/`, built-in `packs/`, `schemas/`, `templates/` and any shipped `stacks/` definitions. Resolve these relative to the installed distribution using the selected runtime's resource APIs or an equivalent packaged resource root, never relative to the caller's working directory or a development checkout. Keep a single canonical source; packaging may copy resources during the build without creating maintained platform-specific variants.

Project resources are separate: `.engkit/project.yaml` and `.engkit/packs/` resolve against the explicit project root. In M0, document the artifact format and resource inclusion rules; extend the artifact check as resources land in later milestones. Test the built, non-editable distribution in an isolated environment with the source checkout unavailable and a different working directory. `--help` alone is not sufficient distribution validation.

## 5. Design decisions and invariants

1. **Canonical source only:** `skills/<name>/SKILL.md` is authoritative. Installation copies the entire skill directory, including `references/` and `scripts/` if present.
2. **Safe naming:** Permit lower-case ASCII letters, digits, and hyphens; require names to match their directory names. Reject traversal, absolute names, and symlinked source files that escape the toolkit root.
3. **No overwrite by default:** If destination exists and is identical, report `already installed`; if different, report `conflict` with guidance. In a later task, add opt-in `--force` only with backup/rollback safeguards.
4. **Atomic per-skill installation:** Stage the copy in a temporary sibling directory, validate contents, then publish without replacing an existing destination. A preflight existence check followed by an unconditional rename is not sufficient. Use a platform-supported no-replace commit mechanism, or a documented synchronization/reservation protocol with equivalent guarantees for the supported threat model. If the runtime/platform cannot provide the guarantee, fail safely and report the unsupported operation. Clean only staging files owned by the current operation after errors.
5. **Explicit scope:** Default to project scope, rooted at `--project-dir` or current working directory. Global scope must be explicitly requested.
6. **No shelling out unnecessarily:** Use the selected language's filesystem APIs for copy/validation. Never execute scripts contained in skills during install/validate.
7. **Project files are sacred:** Do not auto-modify existing `CLAUDE.md`, `AGENTS.md`, IDE configs, Git hooks, or unrelated source files.
8. **No telemetry:** Do not transmit repository paths, prompt content, or installed skill data.
9. **Evidence over confidence:** All skill outputs must distinguish inspected code, run tests, and hypothetical risks.
10. **Keep dependencies small:** Prefer the selected runtime's standard library where practical. Use a small, pinned/tested dependency for YAML frontmatter if robust parsing cannot be accomplished safely without one. Do not create an incomplete home-grown YAML implementation.

### Concurrent installation and destination safety

- Two installers targeting the same skill must not overwrite each other. After another writer wins publication, inspect the resulting destination safely: identical contents yield `already installed`, differing contents yield `conflict`; an active reservation may yield a retryable `busy` failure. Do not report success before a complete installation is visible.
- If a destination appears or changes between inspection and publication, preserve it. Never delete an existing destination as a way to retry a failed rename.
- Resolve the user-supplied project/home root once; reject symlinks in the managed destination path below that root, including existing platform/skills parents and the skill destination. Protect validation-to-write boundaries with safe filesystem operations; document OS-specific guarantees and limitations in the M3 ADR. Do not claim protection against hostile concurrent parent replacement unless verified.
- Test concurrent identical and differing installs, a destination created just before publication, symlinked destination parents, and cleanup after failures. Confirm that every pre-existing file remains unchanged and that no write escapes the resolved root.

## 6. Skill contracts

### 6.1 Common metadata

```yaml
---
name: systematic-debugging
description: Investigate software bugs and identify root causes using code evidence, reproduction, logs, and tests.
---
```

Each skill should provide:
- **When to use:** Clear trigger conditions and out-of-scope cases.
- **Objective:** What successful work looks like.
- **Inputs:** Codebase, symptom, diff, requirements, tests, logs as applicable.
- **Workflow:** Practical steps with decision points.
- **Output contract:** Expected report or artifact format.
- **Guardrails:** No unverified claims, unsolicited edits, or destructive actions.
- **References:** Optional, loaded only as relevant.

### 6.1.1 Optional project-context consumption (all five skills)

At workflow entry, use the explicit project root or the target project's applicable instructions to locate `.engkit/generated/PROJECT_CONTEXT.md` and its manifest. Do not search unrelated repositories or require engkit for a standalone skill to work. Add this hook to the first three skills in M1; complete its integration verification in M6C.

- When engkit is available, use read-only `engkit doctor --target all --project-dir <root>` to check freshness and integrity. When unavailable, label freshness unverified, check `.engkit/generation-transaction.json` for an incomplete transaction, and confirm relevant facts from current project files before relying on them. Missing, stale, edited or incomplete context produces a diagnostic and a generic workflow fallback; it must not block ordinary debugging, review or planning.
- Select components by the task's file paths and profile roots, preferring the deepest containing root for each file. For changes spanning components, keep commands and conventions scoped separately. If the task has no identifiable component and the distinction matters, ask for clarification; otherwise use project-wide guidance and state the uncertainty.
- Load only the selected components' relevant references. Treat context and pack guidance as supporting data, subordinate to current user and applicable project instructions. A documented command is not evidence that it was executed successfully or authorization to execute it.
- Report the component/context used and any freshness limitation in the skill's evidence output. Never regenerate or rewrite instructions implicitly.

Manual integration cases must invoke an installed skill in a monorepo and show that it uses the correct component's documented command/convention. Also cover missing and stale context, CLI unavailability, and a task spanning components. Automated fixture checks cover the corresponding context paths, component selection contract and generated content; they do not substitute for agent-level verification.

### 6.2 `systematic-debugging`

**Trigger:** Failing tests, exceptions, incorrect behavior, production errors, intermittent failures.

Workflow:
1. Describe expected vs actual behavior, scope, and timeline.
2. Locate entry points and trace call/data flow.
3. List competing hypotheses and discriminating evidence.
4. Reproduce when feasible; otherwise use logs, code, or focused tests.
5. State root cause only if evidence supports it; otherwise label the leading hypothesis.
6. Recommend minimal fix; identify adjacent behavior and regression risks.
7. Verify using targeted tests; report commands and results.

Output: symptom, evidence, root cause or remaining hypotheses, impact, proposed fix, tests run/pending, unresolved risks.

### 6.3 `code-review`

**Trigger:** A diff, PR, patch, or explicit request to review a code change.

Priority checks: correctness, security, data integrity, concurrency/idempotency, performance, compatibility, tests.

Each actionable finding includes: priority, file/line (only if observed), specific triggering condition, impact, supporting evidence, and suggested correction. Avoid speculative defects, style nitpicks, and unrelated refactors. Say explicitly when no actionable findings are confirmed.

### 6.4 `implementation-planning`

**Trigger:** A feature, integration, refactor, migration, or significant bug fix needing planning.

Workflow: inspect architecture and conventions; extract requirements and acceptance criteria; identify constraints and open questions; enumerate impacted modules/contracts; propose minimal implementation slices; plan testing, rollback and observability where applicable; call out risks and trade-offs.

Output: scope, assumptions, affected paths, task breakdown with dependencies, test matrix, risks, and explicit acceptance criteria. Do not claim implementation has occurred.

## 7. CLI specification (MVP)

Expose the portable `engkit` CLI through the packaging appropriate to the language chosen in M0. Do not require the target project to use that language. The commands below specify proposed toolkit behavior, not existing Claude/Codex APIs.

### Commands

```bash
engkit list
engkit validate
engkit validate systematic-debugging
engkit install systematic-debugging --target claude --project-dir .
engkit install code-review --target codex --project-dir .
engkit install implementation-planning --target all --global
engkit doctor --target all --project-dir .
```

**`list`:** Print available canonical skills and brief descriptions. No modifications.

**`validate [name]`:** Validate one or all skills; return nonzero on invalid metadata/files. Print exact path and reason.

**`install <name> --target {claude,codex,all} [--project-dir PATH | --global]`:** Validate source; create destination parents; stage and copy skill; report installed/already-installed/conflict/error. Project root must be resolved safely. Prevent path traversal and refuse malicious symlinks. For `--target all`, show per-target results and return failure if any target fails; do not claim an all-or-nothing transaction across platforms unless implemented.

**`doctor`:** Read-only inspection: environment, installed skills, destination directories, source-vs-installed status; warn if both platforms cannot be verified. Do not require their CLIs just to inspect directory layout.

**Error behavior:** Stable nonzero exit codes for invalid input/conflict/IO failures; errors human-readable and never swallowed. Do not delete prior installation on a failed operation.

**Future (not MVP):** `uninstall`, `update`, general installation `diff`, pack installation, installation `--force` with backups, and installed-skill version manifests. Generation dry-run, inspect JSON output, a generation manifest and `project generate --replace-generated` with backup/recovery are included in M6. Replacement of generated context never authorizes replacement of installed skills.

## 8. Milestone work breakdown

### M0 — Repository inspection and scaffold

**Tasks**
- [ ] Examine repository tree, current Git state, existing packages/tests, and user instructions.
- [ ] Verify current official compatibility requirements for Claude Code and Codex skills; document any differences.
- [ ] Compare suitable implementation languages against CLI distribution, cross-platform support, dependency footprint, schema parsing and maintenance; record the choice in an ADR.
- [ ] Create package layout, ecosystem-specific manifest, `.gitignore`, project README, tests structure.
- [ ] Document runtime minimum version and dependency policy. This choice must not constrain supported target-project stacks.
- [ ] Record artifact format, bundled resource lookup and a non-editable distribution smoke-test procedure in the ADR.

**Acceptance criteria**
- [ ] Installed `engkit --help` works using the chosen runtime.
- [ ] Package is importable using the documented local setup.
- [ ] The built distribution can locate an initial bundled resource from an unrelated working directory without access to the source checkout; extend this check as M1–M6 resources land.
- [ ] No unrelated files are changed.

### M1 — Author the three portable MVP skills

**Tasks**
- [ ] Implement `systematic-debugging/SKILL.md` with clear evidence classifications.
- [ ] Implement `code-review/SKILL.md` with severity rubric and actionable finding format.
- [ ] Implement `implementation-planning/SKILL.md` with scoped, verifiable task planning.
- [ ] Add brief supporting references only where justified.
- [ ] Include realistic, **synthetic** examples, not private production data.

**Acceptance criteria**
- [ ] All three have valid `name` and `description` metadata.
- [ ] All names match their directories.
- [ ] Each has explicit use conditions, workflow, output contract, and guardrails.
- [ ] No skill implicitly authorizes edits, production access, or destructive operations.
- [ ] Each skill includes the optional context-consumption and generic fallback contract in section 6.1.1.

### M2 — Catalog and validation

**Tasks**
- [ ] Implement deterministic skill discovery and metadata extraction.
- [ ] Validate frontmatter with clear error messages.
- [ ] Validate naming, required files, missing references where discoverable, path containment, and duplicates.
- [ ] Implement `list` and `validate` commands.
- [ ] Cover malformed metadata and hostile paths in tests.

**Acceptance criteria**
- [ ] Valid skills enumerate consistently.
- [ ] Invalid skills return nonzero and useful error locations.
- [ ] Tests include missing `SKILL.md`, malformed YAML, duplicate names, invalid name, symlink escaping root.

### M3 — Platform adapters and safe installer

**Tasks**
- [ ] Implement centralized path mapping for Claude/Codex and project/global scopes.
- [ ] Implement safe stage-copy-rename installation (no overwrite).
- [ ] Detect identical installation versus conflicting installation.
- [ ] Implement `--target all` with truthful per-target reporting.
- [ ] Add tests using temporary home/project roots and simulated permission/copy failures.
- [ ] Implement and document the concurrent publication and destination-parent safety contract in section 5.
- [ ] Exercise installed `list`, `validate` and `install` from a separate project using the built distribution, without access to the source checkout.

**Acceptance criteria**
- [ ] All four scope/platform combinations produce correct paths.
- [ ] Files and nested references copy correctly.
- [ ] Repeated install is idempotent; different existing files remain untouched.
- [ ] Failed copy leaves no partial skill directory.
- [ ] Installer never executes bundled scripts.
- [ ] Concurrent writers and a destination appearing before commit cannot replace existing contents; unsafe destination parents fail without writes outside the resolved root.

### M4 — Diagnostics and documentation

**Tasks**
- [ ] Implement read-only `doctor` command.
- [ ] Write README quickstart, examples, contributor workflow, and security guidance.
- [ ] Document confirmed platform differences and manual verification steps.
- [ ] Provide example project-level invocation guidance without overwriting existing instruction files.

**Acceptance criteria**
- [ ] Fresh developer can install a skill using README only.
- [ ] `doctor` reports missing or conflicting installations without modifying them.
- [ ] Docs clearly separate platform-documented behavior from unverified assumptions.

### M5 — Core-toolkit evaluations and checkpoint

**Tasks**
- [ ] Add at least two synthetic cases per MVP skill.
- [ ] Define baseline (without skill) vs skill-enabled evaluation procedure.
- [ ] Grade factual correctness, evidence quality, false positives, regression coverage, and unnecessary work.
- [ ] Add optional token/tool-call cost measurements only when data is available.
- [ ] Run automated tests and document manual Claude/Codex smoke test outcomes.

**Acceptance criteria**
- [ ] Six or more documented evaluation scenarios with expected outcomes.
- [ ] Evaluation template supports honest `pass/fail/not-run` reporting.
- [ ] No invented benchmark scores.
- [ ] README includes limitations and a release checklist.

This checkpoint covers the three M1 skills and four core CLI commands. It is not final MVP release readiness; M6C reruns the full verification and completes the five-skill, ten-case delivery checklist.

## 9. Test strategy

### Automated tests
- **Catalog:** deterministic ordering, description parsing, empty directory, duplicates.
- **Validator:** invalid/missing frontmatter, name/path mismatch, malformed YAML, escaped symlinks, missing references.
- **Installer:** project/global resolution, Claude/Codex/all targets, nested copies, existing identical destination, conflicting destination, partial-copy failures, cleanup, no script execution.
- **Concurrent installation:** identical/differing concurrent writers, destination appearing before publication, symlinked parents, retryable busy status, preservation of pre-existing content.
- **Distribution:** built artifact installed outside the checkout; bundled resources load from an unrelated cwd; installed CLI performs listing, validation, installation and, after M6C, generation.
- **Generation:** unchanged-input no-op, changed-profile conflict, user-edited output conflict, explicit replacement with backup, manifest consistency, injected write/backup failures, interrupted-transaction recovery, and dry-run with no filesystem changes.
- **Local packs:** bundled/project discovery, duplicate IDs, exact dependency versions, missing dependencies, cycles and custom-pack generation from an external project.
- **CLI:** help, valid commands, invalid arguments, errors and exit status.
- **Security:** reject path traversal, refuse source symlinks escaping repo, never clobber existing user content.

### Manual smoke tests (run only where tools are available)
1. Install a skill into a clean sample project for Claude Code; verify discovery and invocation with a controlled prompt.
2. Repeat for Codex; verify discovery and invocation using its current documented flow.
3. Test coexistence with existing `CLAUDE.md` and `AGENTS.md`.
4. Confirm removing the temporary example project does not affect global installation.
5. Record tested versions, OS, commands, observations, and unverified points.
6. After M6C, invoke installed skills with generated monorepo context and verify component-specific commands/conventions; repeat with missing/stale context, unavailable engkit CLI and a cross-component task.

### Eval cases
- **Debugging:** A generic cookie-domain mismatch; a duplicate-processing/race condition in a job worker. Stack-specific variants may be added without becoming core requirements.
- **Review:** A diff introducing a lost-update race; a diff with an N+1 query and misleading tests.
- **Planning:** An API integration with ambiguous idempotency requirements; a datastore schema change requiring a safe migration plan.

For each case, store: prompt, synthetic fixture (if needed), rubric, critical expected findings, disallowed hallucinations, and result template.

## 10. Extension plan after MVP

**Technology packs:** Extend the M6 declarative contract with optional packs for any language, framework, datastore, infrastructure or domain. Names such as `python-django` or `typescript-react` are examples, never a fixed catalog or mandatory defaults. Packs build on core workflows without forking them.

**Composed workflows:** An optional orchestrator guide can chain `implementation-planning` → `code-implementation` → `test-strategy` → `code-review`, skipping unnecessary stages for trivial tasks. Agent-specific orchestration must remain optional.

**External integrations:** Investigate MCP or platform-native tools for GitHub/Jira/logs only after the no-network, local-first skill toolkit works. Require explicit user-granted permissions and least privilege.

**Packaging/release:** Add semantic versioning, changelog, CI matrix (macOS/Linux/Windows where available), reproducible distribution, and clear upgrade behavior.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Different skill discovery across platforms | Thin platform adapters + documented smoke tests |
| Existing skill overwritten | No-overwrite default + conflict detection |
| Malicious paths or symlinks | Strict naming, containment checks, safe copy |
| Partial installation | Stage and rename, cleanup on failure |
| YAML compatibility issues | Use a real parser and tested metadata subset |
| Skills become too verbose | Progressive disclosure via `references/` |
| AI reports guessed root causes | Evidence/hypothesis classification in output contracts |
| Excessive process on simple work | Skills are conditional, composable, and scoped |
| Benchmark overfitting | Diverse synthetic fixtures and baseline comparisons |
| Platform docs evolve | Compatibility matrix, manual checks, targeted adapter updates |

## 12. Initial execution request for Claude Code

Use the following prompt with this plan:

> Read `IMPLEMENTATION_PLAN.md` as the source of requirements. Inspect the repository and any existing `CLAUDE.md` before changing files. Implement M0–M5, then M6A → M6B → M6C incrementally, respecting the non-goals and safety invariants. M5 is a checkpoint; final MVP release readiness follows M6C and section 13. Start by inspecting repository constraints, choosing the toolkit implementation language and distribution/resource strategy with an ADR, and verifying compatibility assumptions. Follow the stack-neutral contracts in section 14 and context-consumption contract in section 6.1.1. Preserve existing project stacks and generate context without running project commands. Verify concurrent no-overwrite installation, custom-pack resolution, packaged-resource lookup and recoverable explicit regeneration. For each milestone, create or update tests, execute them where possible, and report actual results. Prefer small changes and avoid unrelated refactoring. Do not modify global configurations, overwrite existing user files, or run network/install commands without permission. If a milestone is blocked, document the blocker and proceed with independent safe tasks. At completion, provide a concise inventory of implemented features, commands tested, outstanding manual platform verification, and any gaps against the acceptance criteria.

## 13. Delivery checklist

- [ ] M0–M5 and M6A–M6C acceptance criteria satisfied, with verification evidence recorded.
- [ ] Repository and packaging established; built distribution works from a separate project without access to the source checkout.
- [ ] Five portable skills written and validated, including optional context consumption and generic fallback.
- [ ] CLI supports `list`, `validate`, `install`, `doctor`, `project inspect`, `stack validate`, `project define` and `project generate`.
- [ ] Project and global installation supported for Claude and Codex.
- [ ] Installation idempotent and does not overwrite existing content, including concurrent publication and unsafe destination-parent cases.
- [ ] Versioned profile/stack/pack schemas, merge rules and compatibility diagnostics implemented.
- [ ] Existing, new, monorepo and unknown-stack project workflows supported without changing project architecture or executing project scripts.
- [ ] Local custom stacks/packs work without core-code changes; duplicate IDs and dependency failures are explicit.
- [ ] Generation supports deterministic output, read-only dry-run, conflict reporting and explicit replacement with backup/recovery.
- [ ] `doctor` checks input freshness, output integrity, unresolved components, pack conflicts and interrupted generation.
- [ ] Skill integration with component context has manual results recorded, or is explicitly pending for unavailable platforms.
- [ ] Automated tests pass and test results are recorded.
- [ ] Manual platform tests recorded (or explicitly pending).
- [ ] README and contributor docs complete.
- [ ] Ten or more synthetic evaluation cases included, at least two per skill.
- [ ] Existing/new-project, monorepo, custom-pack, regeneration and recovery workflows documented.
- [ ] Limitations, known risks, and next-phase work documented.

## 14. Stack-neutral project support — required architecture and M6

### 14.1 Intent and scope

The toolkit must adapt engineering workflows to an existing project or define a suitable stack for a new one. No language, framework, database, hosting provider, architecture style, or package manager is a mandatory target-project dependency.

Separate four concerns:
1. **Core workflows:** universal investigation, review and planning methods.
2. **Project profile:** observed components, constraints, conventions and commands.
3. **Technology packs:** optional focused knowledge and detection rules.
4. **Platform adapters:** rendering and installation for Claude Code and Codex.

The toolkit itself needs an implementation language; choosing it does not choose a stack for projects that consume its skills. “Any project” means extensible definitions and a useful generic fallback, not claiming complete expertise or verified compatibility with every technology.

### 14.2 Existing-project workflow

Inspect → detect → reconcile explicit configuration → validate → generate context → install selected skills.

- Inspect manifests, lockfiles, build configuration, CI and documented instructions as data. Never execute them during detection.
- Support multiple components with independent languages and tools. A root manifest does not determine every subproject.
- Record evidence as relative path plus key or observed value; avoid secrets and full file dumps.
- Treat absent evidence as unknown, not proof that a technology is absent.
- Explicit user configuration wins over inferred values. Component overrides win over project defaults. Existing instructions remain authoritative constraints; conflicting sources produce diagnostics.
- Emit candidates and evidence for ambiguous detection. Do not silently select a package manager when conflicting lockfiles exist.
- Skip generated artifacts, vendored dependencies and cache directories; bounded traversal and safe symlink handling are required.
- Unknown stacks still receive portable engineering workflows with unresolved stack details clearly listed.

### 14.3 New-project workflow

Requirements → candidate stacks → trade-off comparison → selected definition → validation → context generation.

Capture product type, workload, team experience, budget, operational constraints, integrations, security needs and deployment environment. Ask only questions whose answers change a material choice.

The agent's `stack-selection` skill proposes two or three viable options, gives reasons and assumptions, then records the selected option. The offline CLI validates and renders the definition; it does not pretend to independently choose the best stack through heuristics.

Avoid fashionable defaults. Prefer the simplest viable stack for the requirements. Explain unresolved constraints and evidence needed. The agent must verify current versions and compatibility through official documentation when network access is available; otherwise label them unverified and avoid inventing exact versions.

MVP generation means project profile, engineering context and optional instruction drafts. Application scaffolding, package installation, service provisioning and deployment are separate future capabilities.

### 14.4 Data contracts

Store reusable stack definitions in `stacks/<id>.yaml`; store a project's explicit profile in `.engkit/project.yaml`. Use versioned schemas and a real parser. YAML below illustrates the intended contract, not a fixed stack:

```yaml
schema_version: 1
project:
  name: sample-project
  mode: existing
  constraints:
    deployment: existing-environment
components:
  - id: service
    root: services/service
    stack:
      languages: []
      frameworks: []
      datastores: []
      build_tools: []
      package_managers: []
    commands:
      test:
        argv: []
        cwd: services/service
        status: unknown
    conventions:
      references: []
    packs: []
    evidence: []
    unresolved:
      - Test command must be obtained from project documentation.
overrides: {}
```

- Each stack item supports an identifier and optional version constraint.
- Evidence records source path, source field, detected value and confidence category: confirmed, inferred or unknown.
- Commands use argument arrays, a contained working directory, provenance and verification status; rendering never executes them.
- Validate component IDs, contained roots, duplicate entries, pack references, version syntax and required schema fields.
- Define merge behavior explicitly: scalar override; maps recursively merged; lists replaced unless a schema field declares keyed merging. Components merge by ID; conflicting evidence is retained as a diagnostic.
- Reject incompatible known combinations using declared compatibility rules. Unknown compatibility is a warning, never a fabricated pass.
- Runtime or infrastructure requirements may be absent or unknown. Do not require web-specific fields for libraries, mobile apps, embedded systems, data pipelines or command-line projects.

### 14.5 Technology-pack contract

A pack contains a versioned manifest, optional detection rules, compatibility constraints, contextual references and rendering fragments. It must declare:
- ID, version, description and supported profile-schema range.
- Applicable component capabilities or stack identifiers.
- Optional pack dependencies and explicit conflicts.
- Declarative detection rules over bounded file paths and parsed keys.
- Reference files and template inputs/outputs.

No executable plugin loading, lifecycle hooks or arbitrary command execution in MVP. Reject unsafe paths, missing references, dependency cycles and invalid templates. Unknown packs must fail clearly while generic core workflows remain usable.

Ship a small set of synthetic representative packs to prove extensibility, including at least one user-defined pack. New stack IDs may be defined without editing the core code. Detection rules may cover common manifests, but must not be the only way to define a stack.

**Local registry and resolution (MVP):**
- Built-in packs come from the installed distribution's resource root. User-defined packs live at `<project>/.engkit/packs/<id>/pack.yaml`, with references and fragments contained in that pack directory. No pack installation command or network lookup is required: users create or copy declarative files there.
- Discover both sources deterministically by ID. Neither source silently overrides the other: duplicate IDs, including identical versions or different versions, are errors naming both paths. A custom alternative must use a distinct ID. Support one available version per ID in MVP.
- Profile `packs` entries identify an ID and may pin an exact version. Pack dependencies specify an ID and exact version; resolve transitively from the same local registry, validate schema compatibility and conflicts, and order dependencies before dependents with ID as the tie-breaker. Do not fetch dependencies or select a guessed nearest version. Missing IDs, version mismatches and cycles produce actionable errors before generation writes anything.
- `inspect`, `project define`, `project generate` and `doctor` use their `--project-dir` or cwd as registry context. `stack validate` accepts `--project-dir` with the same default; the stack file's directory does not implicitly become the project root. Relative reference paths inside a pack always resolve against that pack, independent of cwd.
- Record resolved IDs, exact versions, project-relative or bundled origins, and content hashes in the generation manifest. Do not embed machine-specific absolute install paths in generated artifacts. Reject symlink escapes from project pack roots and bundled resource roots.
- An invalid selected pack or dependency blocks dependent generation. Unrelated invalid packs are reported by inspection/doctor without disabling standalone generic skills or generation that selects only valid packs. Duplicate registry IDs are always a registry error; generic skills remain usable without the registry.

### 14.6 Context generation and skill composition

Generate a portable `.engkit/generated/PROJECT_CONTEXT.md` from the resolved profile, then optional Claude/Codex instruction drafts inside the generated directory. Do not overwrite existing `CLAUDE.md` or `AGENTS.md`; provide a short inclusion proposal respecting each platform's verified behavior.

Context contains component roots, observed stack, relevant conventions, documented commands, selected pack references, constraints and unresolved assumptions. Load only references relevant to the task's component and workflow.

Core skill + relevant component context + optional technology guidance produces the workflow through the context-consumption hook required by section 6.1.1. Context itself is optional: each skill can run without it; when usable context exists, the hook selects the relevant components. Packs refine implementation details without replacing evidence standards or user instructions. Platform instruction drafts are optional convenience artifacts, not the only mechanism by which skills discover context.

Generation is deterministic: identical inputs produce identical bytes. Record the resolved profile, observed input paths and hashes, schema/template versions, target selection, resolved packs and output hashes in `manifest.json`. Hash the generated files other than the manifest itself; do not include timestamps, absolute machine paths or transaction IDs in deterministic output. Freshness checks must detect new or removed relevant detection inputs, not just changes to previously recorded files. `doctor` distinguishes stale inputs, edited/missing outputs and incomplete generation.

**Regeneration and recovery contract:**
- An initial generation into an absent directory writes context, selected platform drafts, referenced generated assets and `manifest.json` under `.engkit/generated/`. For an existing directory, identical desired output with valid existing output hashes is a no-op. Different desired output, user-edited output or an absent/invalid existing manifest is a conflict by default; report paths and the explicit replacement command.
- `project generate --replace-generated` authorizes replacement of the generated bundle only. It never replaces a profile, installed skill, `CLAUDE.md` or `AGENTS.md`. The bundle is context plus the drafts/assets selected by the current invocation; changing `--target` is an input change and may remove previously generated drafts after backup.
- Before mutation, validate inputs and destination containment, render and validate a complete staged bundle, and acquire an exclusive generation lock. Use the destination-parent safety rules in section 5. Detect changes since inspection before committing; abort if another writer or manual edit changed the snapshot. A lock used only by engkit must not be described as protection against every external writer.
- For explicit replacement, create and verify a backup of the entire previous generated directory, including user edits and unrecognized files, at `.engkit/backups/<transaction-id>/`. Refuse unsafe entries rather than following symlinks. Preserve unrecognized files in the new directory; if they collide with new generated paths, fail with a conflict. The first generation has no prior bundle to back up. A backup failure leaves the active bundle untouched.
- Keep the journal at `.engkit/generation-transaction.json`, the exclusive lock at `.engkit/generation.lock`, and operation-owned staging at `.engkit/staging/<transaction-id>/`, outside the generated bundle. These paths and backups are the explicit exceptions to generated-only output writes; never modify unrelated project files. Document safe stale-lock handling and journal fields in M6C before implementation. Never reclaim a lock held by a live writer; recovery acquires the same exclusive lock. MVP retains backups until the user removes them explicitly.
- Publish files and the matching manifest as one recoverable operation. Do not claim cross-file atomicity unless the chosen filesystem mechanism provides it. Where publication requires multiple steps, persist a transaction journal before mutation and commit the manifest last. While the journal indicates an incomplete transaction, `doctor` and skill consumers must treat the bundle as unusable regardless of individual file contents.
- On a handled write/commit failure, restore the prior bundle (or the prior absence for first generation) and return failure. If rollback fails or the process is interrupted, retain the journal and backup, report their paths, and block subsequent generation. `project generate --recover-generated` explicitly restores the prior state using the journal, validates it and clears transaction state only after successful recovery; it does not also generate a new bundle. Never recover or delete backups automatically from read-only `doctor`.
- `--replace-generated` and `--recover-generated` are mutually exclusive. `--dry-run` may accompany either to report proposed changes/recovery without creating directories, locks, staging, backups or journals. Recovery must validate all journal paths and detect unexpected post-interruption edits; on mismatch, preserve everything and report manual recovery instructions instead of overwriting those edits.

### 14.7 Proposed CLI additions

```bash
engkit project inspect --project-dir . --json
engkit stack validate --file stacks/custom.yaml --project-dir .
engkit project define --stack stacks/custom.yaml --project-dir .
engkit project generate --project-dir . --dry-run
engkit project generate --project-dir . --target all
engkit project generate --project-dir . --target all --replace-generated --dry-run
engkit project generate --project-dir . --target all --replace-generated
engkit project generate --project-dir . --recover-generated
engkit doctor --target all --project-dir .
```

- `inspect`: read-only structured detection report; does not persist a profile.
- `stack validate`: validate a definition, referenced packs from the selected project registry, and known compatibility constraints.
- `project define`: create an explicit profile from a supplied definition; refuse an existing different profile. For existing projects reconcile detection and report contradictions before writing.
- `project generate`: validate, resolve profile and selected packs, then emit project context and platform drafts. `--dry-run` only reports the proposed operation. Apply no-op/conflict, `--replace-generated` and `--recover-generated` semantics from section 14.6; report backup paths and recovery status when applicable. Return actionable errors for ambiguity that affects output.
- `doctor`: additionally report unresolved components, incompatible packs, stale inputs, edited/missing outputs and incomplete generation. It performs no repair or recovery writes.

CLI stack recommendation is not required. Agent-guided selection must work without an API key or embedded LLM dependency.

### 14.8 Additional skill contracts

Add `project-discovery` and `stack-selection` as portable workflows:
- **project-discovery:** map components, evidence, architecture, conventions and documented commands; produce a profile proposal with unknowns; preserve existing architecture.
- **stack-selection:** extract constraints, compare candidates, record choice and reasons, define a reusable stack and test strategy; generate reviewable context.

All five core skills stay independent of a particular stack. Technology names appear only in optional examples and references. Stack-selection may recommend technologies; it may not silently migrate an existing project.

### 14.9 M6 — Profiles, detection, stack definitions and generation

Implement M6A → M6B → M6C after M0–M5. Each submilestone has its own verification gate. Logical modules: profiles, schemas, detection, packs, resolution, generation. Choose file layout and extensions to match the implementation language selected in M0.

#### M6A — Schemas and profile resolution

Tasks:
- [ ] Define versioned profile, stack and pack schemas, merge rules and validation diagnostics.
- [ ] Add profile loader/resolver with explicit overrides, component scopes and provenance.
- [ ] Specify exact pack dependency versions and local registry inputs for M6B; no implicit network resolution.

Acceptance criteria:
- [ ] Profiles represent existing/new projects, mixed-component monorepos and unknown stacks without web-specific mandatory fields.
- [ ] Explicit configuration wins over supplied inferred values; contradictions remain visible.
- [ ] Tests cover schema versions, malformed input, contained paths, duplicate IDs, keyed component merging and list replacement.
- [ ] Parsing/resolution has no filesystem writes or project-command execution.

#### M6B — Detection, local packs and definition commands

Tasks:
- [ ] Add bounded read-only detection with evidence, ambiguity reporting and unknown-stack fallback.
- [ ] Implement bundled/project pack discovery and dependency/conflict resolution from section 14.5.
- [ ] Implement `project inspect`, `stack validate` and `project define` using the M6A contracts.
- [ ] Extend `doctor` with profile, component and pack diagnostics.
- [ ] Document local pack layout and existing/new-project definition workflows.

Acceptance criteria:
- [ ] Detection distinguishes components and their commands without executing manifests/scripts or modifying project architecture.
- [ ] A new project accepts an explicit stack; an unknown stack remains usable through manual definition.
- [ ] A user-defined stack/pack in a project outside the toolkit checkout works without core-code changes or a pack install command.
- [ ] Duplicate pack IDs, exact-version mismatches, missing dependencies, cycles and known compatibility conflicts are diagnosed before dependent writes.
- [ ] `inspect` remains read-only; `define` refuses a different existing profile and preserves unrelated files.

#### M6C — Generation, skill integration and final release verification

Tasks:
- [ ] Implement deterministic generation, manifest integrity/freshness checks and write-free dry-run.
- [ ] Implement explicit replacement, verified backup, interrupted-transaction reporting and recovery from section 14.6.
- [ ] Author `project-discovery` and `stack-selection`; verify the context-consumption hook across all five skills.
- [ ] Extend `doctor` with freshness, output integrity and incomplete-transaction diagnostics.
- [ ] Document monorepo context selection, custom-pack generation, regeneration and recovery.
- [ ] Evaluate the two new skills with at least two synthetic cases each; rerun core tests and record the full ten-case evaluation status.
- [ ] Run built-distribution tests outside the source checkout and final platform smoke tests where available.

Acceptance criteria:
- [ ] Existing, new, mixed-component and unknown-stack projects receive appropriate context without scripts, package installation or application scaffolding.
- [ ] Repeated unchanged generation is a no-op; profile changes and user edits conflict unless replacement is explicit.
- [ ] Backup/write/commit failure injection and interruption tests preserve the previous state or leave a clearly recoverable transaction; no incomplete bundle is reported as fresh.
- [ ] Recovery restores the prior state, preserves backups and refuses unexpected intervening edits; dry-run creates no artifacts for generation, replacement or recovery.
- [ ] A built distribution runs `list`, `validate`, `install` and `project generate` from an unrelated cwd, including a local custom pack, with no source-checkout access.
- [ ] Installed skills use the correct component commands/conventions, fall back when context is missing/stale/incomplete, verify facts before using context of unverified freshness, and handle cross-component work without mixing commands.
- [ ] Claude/Codex outputs use verified adapter behavior; unavailable agent-level checks are marked pending, not inferred from fixture tests.
- [ ] Section 13's five-skill, ten-case final delivery checklist has evidence and explicit outstanding verification recorded.

### 14.10 Verification matrix and final delivery extension

Use independent synthetic fixtures: a JVM service, a Go CLI, a Rust library, a JavaScript app, a mixed-language monorepo and an unidentified custom project. These are test coverage examples, not required supported-stack defaults.

Automated checks cover parsing errors, ambiguous manifests, explicit overrides, component boundaries, unknown identifiers, schema versions, unsafe paths, bundled/project pack lookup, duplicate pack IDs, exact-version dependency failures, cyclic dependencies, compatibility conflicts, deterministic output, no-overwrite behavior, and input/output freshness detection. Include regeneration after profile changes and user edits, verified backups, injected backup/write/commit failures, interrupted recovery, concurrent generation rejection, and write-free dry-runs. Run a distribution fixture with the source checkout unavailable. Detection and generation must work without network access or executing fixture commands.

Selection evaluations include a constrained new project, conflicting requirements, an existing project where migration would be unnecessary, and a custom stack absent from built-in packs. Grade reasoning, constraint adherence, honest unknowns and suitability; do not demand a single fashionable answer.

Final delivery includes M0–M5 and M6A–M6C, five portable skills, profile/stack/pack schemas, discovery and generation CLI commands, at least ten skill evaluation cases, and documentation for custom stacks and recovery. Section 13 is the consolidated delivery checklist. Future application scaffolding must be separately specified and authorized.

