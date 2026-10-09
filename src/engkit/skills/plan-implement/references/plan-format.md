# Plan file format

Load this when writing the plan file. `/implement-plan` identifies slices only by this format.

Each slice is a heading `### Slice N: <title>` (N counts from 1 in dependency order), followed
by these fields:

```
### Slice 1: <title>
- Purpose: <one sentence>
- Files: <path - create | edit | delete>
- Depends on: <slice numbers> or none
- Verification: <command (argv, cwd)> or manual check: <what the user checks>
```

Rules:
- Do not give a plan file a slug that ends in `-ui-spec`. UI specs are only files named
  `*-ui-spec.md` or `*-ui-spec-<N>.md`, written by `/design-ui`.
- Put the slices under a `## Slices` heading; keep `## Progress` for `/implement-plan`.
- When converting a plan from `/bug-investigate` or `/stack-select`, leave the source file
  untouched; the converted plan is a new file that cites the source path.
