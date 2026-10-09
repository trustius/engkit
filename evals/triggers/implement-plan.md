# Trigger evals: implement-plan

Synthetic prompts. Run them as described in README.md.

## Should trigger

1. /implement-plan docs/plans/2026-10-09-export-rate-limiting.md
2. Build the next slice of the CSV export plan in docs/plans/2026-10-02-csv-export.md.
3. The plan in docs/plans/2026-09-28-user-key-migration.md is approved. Start implementing it, one slice at a time.
4. Continue the rate limiting plan from where the Progress table stopped; slice 2 failed last time.
5. Implement slice 1 of docs/plans/2026-10-05-search-filters.md and verify it with the commands in the plan.

## Should not trigger

1. Write a plan for adding rate limiting to the export API before any code is written.
2. Review the attached diff that implements slice 1 of the export plan.
3. The export test fails with a KeyError after the last change. What is the root cause?
4. What does slice 3 of docs/plans/2026-10-02-csv-export.md mean? Explain it, do not build it.
5. Fix the typo in the README heading.

### Argument cases

- 1. With argument: `/implement-plan docs/plans/2026-10-09-export-rate-limiting.md` -> Reads the plan and replies with the approval request only (next slice, files to change, verification commands); nothing is edited yet.
- 2. Without argument: `/implement-plan` -> Lists the plans in `docs/plans/` whose `## Progress` is missing or incomplete, newest first, and asks which one to implement.
