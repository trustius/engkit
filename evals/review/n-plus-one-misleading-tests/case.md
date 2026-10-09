# review/n-plus-one-misleading-tests

Skill: change-review

## Prompt

```
Review change.diff. It adds customer names to the order export endpoint. All tests pass in
CI. Typical exports contain 5,000-20,000 orders. Report actionable findings only; do not
edit files.
```

## Fixture

`fixture/` (synthetic, Python-like):

- `change.diff` — `export_orders()` now calls `customers.get(order.customer_id)` inside the
  loop over orders; also renames a local variable and adds a CSV column.
- `repo.py` — repository layer: `CustomerRepo.get` issues one query per call;
  `CustomerRepo.get_many(ids)` already exists and issues one query.
- `test_export.py` — tests that use a mock `CustomerRepo` returning in-memory objects.

## Rubric

Dimensions: factual correctness, evidence quality, false positives, regression coverage,
unnecessary work. Case-specific:

- Ties the N+1 claim to observed code (`repo.py` shows one query per `get`).
- Explains why passing tests are not evidence here (the mock removes the query cost and
  never counts calls).
- Does not over-claim exact latency numbers; any estimate is labelled as such.

## Critical expected findings

1. **N+1 queries:** one customer query per order (up to ~20,000 extra round trips per export)
   introduced inside the loop in `export_orders`.
2. Suggested correction: collect distinct `customer_id`s and use the existing
   `CustomerRepo.get_many`, or a join; handle missing customers explicitly.
3. **Misleading tests:** the tests mock `CustomerRepo`, so they pass regardless of query
   count; propose a test asserting a bounded number of repository/DB calls (e.g. call
   count or query counter) for many orders.
4. Notes the missing-customer case: `get` returns `None` and `.name` would raise
   (`AttributeError`) for orders whose customer was deleted; tests do not cover it.

## Disallowed hallucinations

- Claiming the variable rename or CSV column change is a bug.
- Claiming caching exists or does not exist beyond what `repo.py` shows.
- Precise latency/throughput numbers presented as measured.
- Claiming the tests or a benchmark were run.

## Pass threshold

Findings 1, 2 and 3 hit; no disallowed hallucination; false positives = 2; no dimension
scores 0.
