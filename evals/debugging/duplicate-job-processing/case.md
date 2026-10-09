# debugging/duplicate-job-processing

Skill: bug-investigate

## Prompt

```
Since we scaled the job worker from 1 to 3 replicas, some customers receive the same
invoice email two or three times. It is intermittent and we cannot reproduce it on a laptop.
The worker code, schema and a log excerpt are in this directory. Find the root cause and
propose a fix with a way to verify it. Do not modify files or run anything against a database.
```

## Fixture

`fixture/` — synthetic job worker (Python-like) and SQL schema:

- `worker/worker.py` — poll loop: select a pending job, then mark it running, then process.
- `worker/jobs.py` — `send_invoice_email` side effect (no idempotency guard).
- `schema.sql` — `jobs` table; no claim token, no unique constraint on sent emails.
- `logs/worker.log` — interleaved logs from three replicas processing job 4812 twice.
- `ops-notes.md` — replica change and a red herring (a mail-provider latency incident).

## Rubric

Dimensions: factual correctness, evidence quality, false positives, regression coverage,
unnecessary work. Case-specific:

- Identifies the check-then-act window between `SELECT ... WHERE status='pending'` and the
  unconditional `UPDATE ... SET status='running' WHERE id=?`.
- Uses the log interleaving (two replicas claim job 4812 within milliseconds) as evidence.
- Explains why a single replica never showed it.
- Treats the mail-provider latency note as at most a contributing factor, not the cause.

## Critical expected findings

1. Root cause: non-atomic claim (check-then-claim race). Multiple replicas can read the same
   pending row before any of them updates it; the `UPDATE` does not re-check `status`, and
   the result row count is ignored.
2. Evidence: `worker.log` shows replicas `w-1` and `w-3` both logging `claimed job 4812`.
3. Fix: an atomic claim, e.g. `UPDATE ... SET status='running', claimed_by=? WHERE id=? AND
   status='pending'` and proceed only if one row changed, or a row lock with skip-locked
   semantics where the datastore supports it (labelled as datastore-dependent).
4. Defence in depth: make the side effect idempotent (e.g. a unique record per
   job/invoice before sending), since at-least-once delivery can still repeat on crash.
5. Verification: a concurrency test with two or more workers against one pending job,
   asserting exactly one claim/send; existing single-worker tests do not cover this.

## Disallowed hallucinations

- Claiming the mail provider or retries alone cause the duplicates.
- Claiming the datastore's default isolation level prevents or causes this without
  labelling it as an assumption (the fixture does not specify the engine).
- Inventing a queue/broker, locks or configuration not present in the fixture.
- Claiming a fix was implemented or tests were run.

## Pass threshold

Findings 1, 2, 3 and 5 hit; no disallowed hallucination; no dimension scores 0.
