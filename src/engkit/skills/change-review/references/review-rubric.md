# Review rubric

Load this reference when assigning priorities or when a check area needs more depth.

## Priority levels

| Priority | Meaning | Typical examples |
|---|---|---|
| P0 | Must not merge. Causes data loss or corruption, a security breach, an outage, or breaks a core path for most users under normal conditions. | Unauthenticated access to protected data; destructive migration without a guard; crash on every request. |
| P1 | Should be fixed before merge. Incorrect behavior under realistic conditions, or a significant regression. | Wrong result for a common edge case; race that double-charges on retry; breaking API change without versioning. |
| P2 | Fix soon. Real defect with limited impact or an unlikely trigger; missing tests for risky logic. | Error path leaks a resource; unbounded query on a large but rare input; test that cannot fail. |
| P3 | Minor. Correct but fragile or unclear in a way likely to cause a future defect. | Misleading name on a security-relevant function; undocumented invariant. |

Rules:
- Priority reflects impact times likelihood under stated, realistic conditions.
- If the triggering condition is not established, it is an open question, not a finding.
- Pure style preferences are not findings at any level.

## Check areas

**Correctness:** boundary values, empty and null inputs, error paths, off-by-one, unit or time zone handling, contract changes for callers.

**Security:** authentication and authorization on every new entry point, input validation, injection, path traversal, secrets in code or logs, unsafe deserialization, overly broad permissions.

**Data integrity:** partial writes, transaction boundaries, migrations that are irreversible or lock large tables, lost updates, validation at persistence boundaries.

**Concurrency and idempotency:** shared mutable state, check-then-act races, retries without idempotency keys, ordering assumptions, lock scope and deadlock risk.

**Performance:** work inside loops (repeated queries or calls), unbounded collections or results, missing pagination, hot-path allocations. Report only with a plausible realistic load.

**Compatibility:** public API, schema, configuration, file format and CLI changes; behavior for existing data and clients; rollout and rollback.

**Tests:** changed behavior is exercised; assertions can fail; mocks do not replace the unit under test; negative and edge cases exist for risky logic; no skipped or disabled tests hiding failures.

## Misleading test patterns

- Assertion on a value the test itself set.
- Exception expected but any exception accepted.
- Test passes when the feature is removed.
- Snapshot updated alongside the code without review of the diff.
- Test name claims coverage the body does not provide.

## Synthetic finding example (illustrative only)

- **Priority:** P1
- **Location:** `src/orders/submit.example:42` (observed)
- **Trigger:** client retries after a timeout on submit
- **Impact:** a second order is created; the customer is charged twice
- **Evidence:** handler inserts before checking the request key; no uniqueness constraint in the accompanying migration (verified fact)
- **Correction:** check and record the request key in the same transaction as the insert, or add a unique constraint
