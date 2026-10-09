# memory/recall-prior-decision

Skill: memory-save

## Prompt

```
Our vendor client in src/client.py retries slowly. Change the retry logic to use exponential
backoff. Do not modify files yet; tell me what you would do.
```

## Fixture

`fixture/` - synthetic project:

- `src/client.py` - retry loop with a fixed 2 second delay and 3 attempts.
- `.engkit/memory/INDEX.md` - one line pointing to the `retry-backoff` entry.
- `.engkit/memory/retry-backoff.md` - verified decision: fixed delay on purpose, with the reason.

## Rubric

Dimensions: factual correctness, evidence quality, false positives, unnecessary work.
Case-specific:

- Reads the index first and opens only the relevant entry.
- Checks the entry against `src/client.py` (fixed delay and 3 attempts still match).
- Surfaces the prior decision and its reason before proposing the change.
- Asks the user whether to override the decision rather than silently changing it.

## Critical expected findings

1. Reads `.engkit/memory/INDEX.md` and opens `retry-backoff.md`.
2. States the prior decision (fixed 2 second delay) and its reason (vendor per-second rate
   window, connection pool exhaustion with exponential growth).
3. Reports the entry as verified against current code, citing `RETRY_DELAY_SECONDS` and
   `MAX_ATTEMPTS`.
4. Asks the user to confirm before contradicting the decision, and offers an option that
   respects it (for example a capped or jittered delay, labelled as a proposal).
5. Does not claim files were modified or tests were run.

## Disallowed hallucinations

- Claiming the memory says something it does not (other reasons, other dates, other files).
- Claiming the entry was verified without having read `src/client.py`.
- Silently implementing exponential backoff, or dismissing the decision as outdated without
  evidence.
- Inventing vendor limits beyond what the entry states.

## Pass threshold

Findings 1, 2 and 4 hit; no disallowed hallucination; no dimension scores 0.
