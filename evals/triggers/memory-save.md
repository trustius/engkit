# Trigger evals: memory-save

Synthetic prompts. Run them as described in README.md.

## Should trigger

1. Please remember in project memory that we decided on queue-based retries for the job runner.
2. /memory-save Remember that we chose queue-based retries and why, so the next session knows.
3. Record this gotcha in project memory: the staging database resets every night.
4. Update the memory entry about the deployment convention; it is out of date.
5. Add a note to project memory that the billing module must never call the provider without an idempotency key.

## Should not trigger

1. Summarize what this function does.
2. Write a changelog entry for the release.
3. Store this API key so I don't have to paste it again.
4. Add a section to the README about local setup.
5. Fix the failing test in the payments module.

### Argument cases

- 1. With argument: `/memory-save staging database resets nightly; do not run migrations there at night` -> When typed by the user, saves that note as one gotcha entry (update instead of duplicating, no secrets); if memory is missing, says to run engkit init.
- 2. Without argument: `/memory-save` -> Proposes candidate entries from this session, shows them, and writes only after the user confirms.
- 3. Automatic invocation with a note (not typed as a command) -> Proposes the entry and writes only after the user confirms.
