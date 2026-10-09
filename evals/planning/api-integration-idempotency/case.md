# planning/api-integration-idempotency

Skill: change-plan

## Prompt

```
We need to switch checkout from our stub to the external payment provider described in
provider-api.md. Produce an implementation plan for the integration. Requirements are in
requirements.md and the current checkout code is in checkout.py. Do not write the
implementation; plan only.
```

## Fixture

`fixture/` (synthetic):

- `provider-api.md` — excerpt of a fictional provider API ("ExamplePay", `api.examplepay.test`).
  Says an `Idempotency-Key` header is "supported" but does not state retention window,
  behaviour on key reuse with a different body, or whether timeouts may still have charged.
- `requirements.md` — product requirements; "customers must never be charged twice" and
  "checkout must survive provider timeouts".
- `checkout.py` — current stub flow: creates order, calls `charge()`, marks paid; retries
  on any exception with no key.

## Rubric

Dimensions: factual correctness, evidence quality, false positives (here: invented API
facts), regression coverage (test matrix), unnecessary work. Case-specific:

- Separates what the provider doc states (verified fact) from what it leaves open (open
  questions / untested assumptions).
- Plan includes scope, assumptions, affected paths, task breakdown with dependencies, test
  matrix, risks, explicit acceptance criteria. Does not claim implementation occurred.

## Critical expected findings

1. Lists the idempotency ambiguities as explicit open questions for the provider (key
   retention window, key-reuse-with-different-body behaviour, outcome of timed-out requests)
   and states the assumption the plan uses until answered.
2. Generates one idempotency key per payment attempt intent (e.g. derived from or stored
   with the order), persisted **before** calling the provider, and reused on every retry.
3. Retry policy: bounded retries with backoff only for retryable/unknown outcomes; on
   timeout, reconcile by querying the provider (the doc has `GET /payments/{id}` / lookup by
   reference) rather than charging blindly; current blanket retry in `checkout.py` flagged as
   a double-charge risk.
4. Local state machine for the payment (e.g. pending -> succeeded/failed/unknown) and handling
   of webhooks/async confirmation if documented, plus a reconciliation path for `unknown`.
5. Test matrix covering: success, decline, timeout then success on retry, timeout with
   charge already applied, duplicate submission (double-click), provider 5xx, key reuse.
6. Rollout: feature flag or staged rollout and rollback path; secrets via configuration
   (placeholder only).
7. The `/change-plan` run writes its plan to `docs/plans/YYYY-MM-DD-<slug>.md` and
   reports the path.

## Disallowed hallucinations

- Stating the provider's key retention period, rate limits or error codes that are not in
  `provider-api.md`.
- Naming a real payment provider's SDK or behaviour as if it applies.
- Claiming any code was written or tests were run.
- Including a real-looking API key.

## Pass threshold

Findings 1, 2, 3 and 5 hit; no disallowed hallucination; no dimension scores 0.
