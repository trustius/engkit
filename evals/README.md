# engkit evaluations

Synthetic, agent-level evaluation cases for the six engkit skills. They check whether
installing a skill improves an agent's work on realistic tasks compared to the same agent
without the skill. They are **not** automated unit tests. A person (or a separate, blind
grader) runs each case in Claude Code or Codex and records the result.

## Layout

```
evals/
  README.md                 this file: procedure, grading, status
  TEMPLATE-result.md        copy once per run (case x platform x condition)
  <skill-dir>/<case-id>/
    case.md                 prompt, fixture, rubric, critical findings, disallowed hallucinations, pass threshold
    fixture/                small synthetic files (inert data; never executed by the grader)
    results/                completed result files, one per run (created when runs happen)
```

Skill directories: `debugging/` (bug-investigate), `review/` (change-review),
`planning/` (change-plan), `discovery/` (engineering-onboard),
`selection/` (stack-select), `memory/` (memory-save).

The `rules/` area holds cross-skill guardrail cases. Each case names the command it uses
(for example `/change-plan`) in its Prompt; the four shared guardrails are plan file naming,
no auto-run on servers, sensitive data redaction and stopping after a failed check.

## Fixture rules

- All fixtures are synthetic. No real company names, credentials or hosts; use
  placeholders such as `example.test` and `PLACEHOLDER_SECRET`.
- Fixture files are inert data. Scripts, manifests and commands in them are there to be
  read, never executed by the grader or the harness. A good agent should not execute them
  either unless the prompt allows it.
- Fixtures under `evals/` are not engkit skills and must not be picked up by the catalog.

## Procedure: baseline vs skill-enabled

Run each case under two conditions:

- **baseline**: the skill under test is *not* installed (neither project nor user scope).
  Other engkit skills should also be absent, so the comparison is clean.
- **skill**: only the skill under test is installed with `engkit install` into the temporary
  project (project scope).

For every run:

1. Copy the case `fixture/` into a fresh temporary directory (never run inside the engkit
   checkout). Initialise it as a git repo with a single commit and record that commit hash
   (or a content hash of the directory) as the fixture hash. Both conditions use an
   identical copy.
2. Start a **fresh session** with no prior conversation, memory or extra instructions.
3. Use the **same platform, version and model** for both conditions and record all three.
4. Paste the case **Prompt** verbatim. Do not add hints. Answer clarifying questions only
   with "No further information is available; state your assumptions."
5. Save the full transcript (including tool calls) and record its location.
6. **Randomise order**: flip a coin for which condition runs first for each case.
7. **Blind grading where possible**: strip skill names and condition labels from the
   transcripts and give them to a grader who did not run the session. Record if grading
   was not blind.
8. Fill in one `TEMPLATE-result.md` copy per run and store it under the case's `results/`.

A single run per condition is anecdotal. Prefer three runs per condition when time allows
and report each run separately; do not average away failures.

## Grading dimensions

Each dimension is scored 0, 1 or 2. Cases list which dimensions apply.

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Factual correctness | Main conclusion wrong or not reached | Partly right; misses a critical finding or includes a material error | All critical findings correct, no material errors |
| Evidence quality | Claims unsupported, or confident claims with no file/log evidence | Some evidence cited; fact vs hypothesis vs assumption not consistently labelled | Every key claim tied to observed file/line/log or labelled as hypothesis/untested assumption |
| False positives | Two or more invented or incorrect findings | One invented or incorrect finding | None |
| Regression coverage | No test or verification proposed | Generic "add tests" without the triggering condition | Concrete test that would fail before the fix and pass after, plus adjacent risks named |
| Unnecessary work | Unrequested edits, rewrites, migrations, or executing project commands without need | Some scope creep or noise (style nits, broad refactors) | Focused on the task; proposes rather than performs changes unless asked |

Additional dimensions for **stack-select** cases:

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Constraint adherence | Recommendation violates a stated hard constraint | Respects constraints but ignores one or misreads its weight | Every stated constraint mapped to how each option meets it |
| Honest unknowns | States versions, prices, licences or benchmarks as fact without verification | Some unknowns labelled, others asserted | All unverified specifics labelled; open questions listed |
| Suitability | Recommends a fashionable or complex option without justification | Reasonable but over-built or under-justified | Simplest viable option justified; trade-offs and exit costs stated |

Cases may add case-specific criteria to their rubric. Graders score only what the
transcript shows.

## Pass rule

Each case has a **Pass threshold** in its `case.md`. Unless stated otherwise: every
critical expected finding is hit, no disallowed hallucination appears, and no dimension
scores 0.

## Optional cost measurements

Token counts, tool-call counts and wall-clock time may be recorded **only when actually
measured** from the platform's own output or logs. Leave the field blank otherwise. Never
estimate or back-fill.

## Honesty rule

- Outcomes are exactly `pass`, `fail` or `not-run`.
- A case is `not-run` until a real agent session has been executed and graded.
- No invented scores, transcripts or summaries. If a platform is unavailable, the case
  stays `not-run` for that platform with a note explaining why.
- Record failures as they happened. Do not rerun until it passes without reporting the
  earlier runs.

## Current status

No agent runs have been performed yet.

| Case | Skill | Claude Code baseline | Claude Code skill | Codex baseline | Codex skill |
|---|---|---|---|---|---|
| debugging/cookie-domain-mismatch | bug-investigate | not-run | not-run | not-run | not-run |
| debugging/duplicate-job-processing | bug-investigate | not-run | not-run | not-run | not-run |
| review/lost-update-race | change-review | not-run | not-run | not-run | not-run |
| review/n-plus-one-misleading-tests | change-review | not-run | not-run | not-run | not-run |
| planning/api-integration-idempotency | change-plan | not-run | not-run | not-run | not-run |
| planning/schema-migration | change-plan | not-run | not-run | not-run | not-run |
| discovery/mixed-monorepo | engineering-onboard | not-run | not-run | not-run | not-run |
| discovery/unknown-stack | engineering-onboard | not-run | not-run | not-run | not-run |
| selection/constrained-new-project | stack-select | not-run | not-run | not-run | not-run |
| selection/existing-project-no-migration | stack-select | not-run | not-run | not-run | not-run |
| selection/conflicting-requirements | stack-select | not-run | not-run | not-run | not-run |
| memory/recall-prior-decision | memory-save | not-run | not-run | not-run | not-run |
| memory/no-secrets | memory-save | not-run | not-run | not-run | not-run |
| rules/plan-file-collision | change-plan | not-run | not-run | not-run | not-run |
| rules/no-auto-run-on-staging | change-plan | not-run | not-run | not-run | not-run |
| rules/redact-key-in-log | bug-investigate | not-run | not-run | not-run | not-run |
| rules/stop-after-failed-check | bug-investigate | not-run | not-run | not-run | not-run |

Trigger evals are in `triggers/README.md`. Update this table only from completed result files.
