# Regenerating and recovering generated context

The design rationale and journal format are in
`adr/0003-generation-transactions.md`.

| Situation | Command | Result |
|---|---|---|
| First run | `engkit project generate --project-dir . [--target all]` | `created` |
| Nothing changed | same | `unchanged` (exit 0, no writes) |
| Profile, packs, detected inputs or `--target` changed | same | `conflict` (exit 3, no writes) |
| You edited a generated file, or the manifest is missing or invalid | same | `conflict` (exit 3) |
| Accept the new output | `... --replace-generated` | backs up the old bundle to `.engkit/backups/<tx>/generated`, then `replaced` |
| Preview | add `--dry-run` | reports only; creates no directories, locks, backups or journals |
| Interrupted run (`.engkit/generation-transaction.json` exists) | `... --recover-generated` | restores the prior state; does **not** generate |
| Another generation running | any | `busy` (exit 5) |

Notes:

- `--replace-generated` replaces only `.engkit/generated/`. It never touches
  `.engkit/project.yaml`, installed skills, `CLAUDE.md` or `AGENTS.md`.
- Files you add inside `.engkit/generated/` outside the engkit-owned paths
  (`PROJECT_CONTEXT.md`, `manifest.json`, `components/`, `references/`,
  `platform/`) are preserved across replacement. Edits to engkit-owned files
  are kept only in the backup.
- Backups are kept until you delete them. `doctor` counts them.
- **Stale lock:** if a run was killed, `.engkit/generation.lock` remains and
  commands report `busy`. When the message says the lock's pid is not running
  on this host, and you have confirmed no engkit process is working on this
  project, delete the lock file and run `--recover-generated`.
- **Manual recovery:** if recovery reports `manual-recovery` (edits after the
  interruption, or a journal that fails validation), nothing was changed.
  Compare `.engkit/generated/` with the backup named in the journal, keep
  what you want, then delete `.engkit/generation-transaction.json`.
- `engkit doctor` is read-only. It reports `fresh`, `stale` (with
  new/removed/changed inputs or pack changes), `modified` (edited or missing
  outputs), `incomplete` (journal present, counted as an error) and lock
  status. It never repairs anything.
