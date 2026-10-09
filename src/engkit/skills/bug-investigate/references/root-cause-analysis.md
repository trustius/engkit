# Root-cause analysis techniques

Load this reference only when the basic workflow is not enough: intermittent failures, multiple interacting causes, failures that cannot be reproduced locally, or regressions with an unclear origin.

## Hypothesis table

Keep a small table and update it as evidence arrives.

| Hypothesis | Predicts | Would rule it out | Evidence so far | Status |
|---|---|---|---|---|
| H1 | ... | ... | ... | plausible hypothesis / verified fact / ruled out |

- Prefer the check that splits the remaining hypotheses most evenly.
- A hypothesis that explains every observation, including the absence of failures elsewhere, ranks above one that explains only the error message.
- Write down what would falsify the leading hypothesis before trying to confirm it.

## Narrowing techniques

- **Differential comparison:** compare a failing and a passing case (input, environment, version, configuration). List every difference, then eliminate them one at a time.
- **Bisection over history:** when a known-good revision exists, bisect commits. Ask before running a bisection that executes project code.
- **Bisection over input:** shrink the failing input until removing anything makes the failure disappear.
- **Boundary tracing:** check the data at each boundary (input parsing, persistence, serialization, external calls) to find where it first becomes wrong.
- **Assertion insertion:** propose temporary assertions or logging at boundaries as text or a diff for the user to apply. Never apply it or edit files yourself.

## Intermittent and environment-dependent failures

Look for shared state, ordering assumptions, timing and concurrency, resource limits, caches, clock and time zone, locale, randomness without a fixed seed, test pollution between cases, and external dependencies. Record the observed failure rate and the sample size; a few passing runs do not prove a fix.

## Distinguishing cause from trigger

- **Trigger:** the event that exposed the defect (a new input, load spike, configuration change).
- **Root cause:** the defect that made the system vulnerable to the trigger.
- **Contributing factors:** missing tests, monitoring gaps or unclear contracts that let it ship.

Report all three when known. Fixing only the trigger usually leaves the defect in place.

## Evidence quality

| Strength | Example |
|---|---|
| Strong | Reproduced failure that disappears with the fix and returns without it |
| Moderate | Log sequence consistent with one hypothesis and inconsistent with the others |
| Weak | Code reading alone; timing correlation with a deployment |

State the strength when presenting a conclusion. Weak evidence supports a **plausible hypothesis**, not a **verified fact**.

## Synthetic example (illustrative only)

A fictional service intermittently returns duplicate records. Hypotheses: H1 retry without an idempotency key; H2 a pagination off-by-one; H3 a cache returning stale pages. Discriminating check: duplicates appear only when the upstream call times out (supports H1, rules out H2, which would be deterministic). Status: H1 is the leading hypothesis until a forced-timeout reproduction confirms it.
