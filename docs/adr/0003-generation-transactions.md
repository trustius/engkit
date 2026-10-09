# ADR 0003: Generation transactions, locking, backup and recovery

- Status: superseded when the generated-context feature was removed (2026-10-09)

## Layout (all under `<project>/.engkit/`)

| Path | Purpose | Lifetime |
|---|---|---|
| `generated/` | The bundle: `PROJECT_CONTEXT.md`, `components/<id>.md`, `references/<pack>/...`, `platform/{claude,codex}.md`, `manifest.json` | Until replaced explicitly |
| `generation.lock` | Exclusive lock (`O_CREAT|O_EXCL`) holding `{pid, host, transaction_id}` | Released at the end of each operation |
| `generation-transaction.json` | Journal | Exists only while a transaction is in flight or unrecovered |
| `staging/<tx>/` | `new/` staged bundle, `previous/` the moved-aside prior bundle, `restore/` during recovery | Removed when the transaction ends |
| `backups/<tx>/generated/` | Verified full copy of the prior bundle, including user edits and unrecognized files | Kept until the user deletes it |
| `backups/<tx>/abandoned-generated/` | An uncommitted bundle moved aside by recovery | Kept until the user deletes it |

These paths and `.engkit/project.yaml` (written only by `project define`) are
the only things engkit writes in a project, apart from skill installs.

## Journal fields

```json
{"journal_version": 1, "transaction_id": "<32 hex>", "operation": "create|replace",
 "had_prior": true, "prior_snapshot": {"<rel path>": "<sha256>"}, "new_snapshot": {...},
 "staging": ".engkit/staging/<tx>", "aside": ".engkit/staging/<tx>/previous",
 "backup": ".engkit/backups/<tx>/generated" | null}
```

Recovery accepts a journal only if every path equals the form derived from
`transaction_id` and every snapshot key is a safe relative path. Anything else
gives a `manual-recovery` report, with nothing changed.

## Generate sequence

1. If a journal exists, refuse (`blocked`) and point to `--recover-generated`.
2. Resolve the profile and packs, then render the whole bundle in memory. Any
   error stops here, before any write.
3. Classify the existing bundle. Absent → create. Intact (manifest valid,
   output hashes match) with identical desired output → `unchanged`.
   Otherwise → `conflict` (exit 3) unless `--replace-generated` was given.
   `--dry-run` reports and stops here.
4. Acquire the lock, then re-check that there is no journal and that the
   bundle snapshot is unchanged since step 3.
5. Write `staging/<tx>/new/`: generated files, then preserved unrecognized
   files, then `manifest.json` last. Verify the hashes.
6. When replacing, copy the current bundle to `backups/<tx>/generated` and
   verify it against the snapshot. On failure, delete the partial backup and
   staging; the active bundle is untouched.
7. Write the journal (fsync).
8. Re-check the snapshot, `rename(generated → staging/<tx>/previous)`, then
   no-replace rename `staging/<tx>/new → generated`. Verify the published
   snapshot.
9. Delete the journal, remove staging and release the lock.

Cross-file atomicity is not claimed. The swap is two directory renames, and
the journal covers the window between them. While the journal exists, `doctor`
reports `incomplete` (an error), and consumers must treat the bundle as
unusable.

## Failure handling

- **Bundle changed after the journal is written, before any rename:** nothing
  was moved, so there is nothing to roll back. Clear the journal and staging,
  release the lock and report `conflict` (exit 3); the user's change stays.
- **Handled exceptions after the journal is written:** roll back. Move a
  fully published new bundle to `staging/<tx>/failed`, rename `previous` back,
  verify against the prior snapshot, then clear the journal and staging and
  release the lock. If rollback itself fails, keep the journal and backup,
  release the lock and print the recovery command.
- **Interruption (process killed):** the journal, staging, backup and lock
  remain. Generation is blocked until recovery.

## Recovery (`project generate --recover-generated [--dry-run]`)

Recovery validates the journal, then compares the current bundle with the
journal's prior and new snapshots:

- current == prior → only clear the transaction state;
- current == new, or absent → restore the prior bundle from `previous/` or from
  the backup, whichever matches the prior snapshot. The copy goes to
  `staging/<tx>/restore`, is verified, then renamed into place. An uncommitted
  new bundle is moved to `backups/<tx>/abandoned-generated`. For a first
  generation, "prior" is absence;
- anything else (edits made after the interruption) → change nothing and print
  manual steps.

Recovery never generates. Backups are never deleted. `--dry-run` writes
nothing. Recovery takes the same lock.

## Stale locks

engkit **never reclaims a lock automatically**. When the lock's host matches
this machine and its pid is not running, the busy message calls the lock
stale and tells the user to delete `.engkit/generation.lock` once they have
confirmed no engkit process is working on the project. This avoids races
where two processes "reclaim" the same lock, or a reused pid is wrongly
treated as stale. The lock coordinates engkit processes only. It does not
protect against other tools or editors writing into `.engkit/generated/`;
the snapshot re-checks (steps 4 and 8) catch most of those cases.

## Determinism

Rendering is a pure function of: the resolved profile, pack manifests,
references and fragments, templates, the target selection and the engkit
version. The output contains no timestamps, absolute paths or transaction IDs.
Upgrading engkit changes the header line, so an upgrade marks bundles stale.
That is intended.
