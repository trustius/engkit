# planning/schema-migration

Skill: implementation-planning

## Prompt

```
We need to rename users.fullname to display_name and add a required region column to
users. See request.md, schema.sql and deploy.md. Produce an implementation plan that is
safe for our live database and rolling deploys. Plan only; do not write migrations or run
anything.
```

## Fixture

`fixture/` (synthetic):

- `request.md` — product request: rename, new required `region`, deadline pressure.
- `schema.sql` — current `users` table (~40M rows noted); datastore engine not named.
- `deploy.md` — rolling deploys (old and new app versions run together for ~20 minutes),
  migrations run before the new version starts, a separate reporting job reads `fullname`.

## Rubric

Dimensions: factual correctness, evidence quality, false positives, regression coverage,
unnecessary work. Case-specific:

- Uses expand -> migrate/backfill -> contract phases across multiple deploys.
- Labels engine-specific behaviour (lock duration for adding columns with defaults, online
  index/ALTER support) as an untested assumption to verify, because the engine is unknown.
- Includes rollback for each phase, observability, acceptance criteria.

## Critical expected findings

1. Do not rename in place or add `NOT NULL` without default in one step: old app instances
   and the reporting job still read/write `fullname` during a rolling deploy.
2. Expand: add `display_name` (nullable) and `region` (nullable or with a safe default);
   app dual-writes `fullname` and `display_name`.
3. Backfill in batches (throttled, resumable, idempotent) for ~40M rows; verify counts.
4. Switch reads to `display_name`; migrate the reporting job; add `NOT NULL` on `region`
   only after backfill is complete and verified (with engine-appropriate validation).
5. Contract: drop `fullname` only in a later release after all readers moved; rollback is
   possible at every step before the drop, and the drop is the irreversible point
   (backup/retention noted).
6. Open question: what `region` value existing users get (no source given) — must be asked,
   not invented.

## Disallowed hallucinations

- Naming a specific datastore engine or version as fact.
- Claiming a particular `ALTER` is lock-free/instant without labelling it as engine-dependent.
- Inventing a source for `region` values for existing users.
- Claiming migrations were written or executed.

## Pass threshold

Findings 1, 2, 3, 5 and 6 hit; no disallowed hallucination; no dimension scores 0.
