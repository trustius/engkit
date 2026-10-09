# review/lost-update-race

Skill: change-review

## Prompt

```
Please review the change in change.diff before it merges. Context: wallet.py is the service
that debits customer credit balances; it runs as several concurrent request handlers against
one shared database. Report actionable findings only. Do not edit files.
```

## Fixture

`fixture/` (synthetic, Python-like):

- `change.diff` — refactors `debit()` from a single conditional `UPDATE` into
  read-in-application, compute, write-back, and adds an audit log entry and a helper.
- `wallet_before.py` — the file before the change (for context).
- `test_wallet.py` — the updated tests (sequential only).

## Rubric

Dimensions: factual correctness, evidence quality, false positives, regression coverage,
unnecessary work. Case-specific:

- Findings carry priority, file/line from the diff, triggering condition, impact,
  evidence and suggested correction.
- No style nits presented as defects (the `amt` -> `amount` rename may be noted as a compatibility question, not a defect).
- Says explicitly which observations are verified from the diff vs hypotheses about runtime
  (e.g. transaction isolation level is not shown).

## Critical expected findings

1. **High — lost update / race:** two concurrent debits read the same `balance`, each writes
   `balance - amount`; one debit is lost. The previous single atomic `UPDATE ... SET balance =
   balance - ? WHERE ... AND balance >= ?` did not have this problem.
2. **High — overdraft:** the `balance >= amount` check is now in application code against a
   stale read, so concurrent debits can drive the balance negative (insufficient-funds guard
   bypassed).
3. Suggested correction: keep the atomic conditional update (check affected row count), or
   use a row lock / optimistic version column with retry; keep the audit insert in the same
   transaction.
4. Tests: `test_wallet.py` is sequential and cannot detect the race; propose a concurrent
   test (two debits on one balance) asserting final balance and no negative balance.

## Disallowed hallucinations

- Claiming SQL injection (all queries are parameterised).
- Asserting as fact that the `amt` -> `amount` rename breaks callers (no callers are in the
  fixture; raising it as a question to verify is acceptable).
- Asserting a specific isolation level as fact.
- Inventing line numbers or files not present.
- Claiming tests were run.

## Pass threshold

Findings 1, 3 and 4 hit (2 strongly expected); no disallowed hallucination; false
positives = 2; no dimension scores 0.
