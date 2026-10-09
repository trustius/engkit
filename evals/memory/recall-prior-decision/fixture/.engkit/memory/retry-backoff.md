---
name: retry-backoff
type: decision
status: verified
updated: 2026-03-02
sources: [src/client.py, docs/vendor-limits.md]
---
Retries use a fixed 2 second delay with at most 3 attempts, not exponential backoff.

Why: the vendor API enforces a per-second rate window and penalises bursts. Exponential
growth made callers hold connections for minutes during an outage and exhausted the pool.
Revisit only if the vendor changes its limit policy.
