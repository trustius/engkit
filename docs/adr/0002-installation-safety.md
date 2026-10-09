# ADR 0002: Installation safety and concurrent publication

- Status: accepted (M3)

## Contract

`engkit install <name> --target {claude,codex,all} [--project-dir P | --global]`:

1. Validate the canonical source skill. An invalid source installs nothing.
2. Resolve the root (project dir or `$HOME`) once with `realpath`. Create or
   verify each managed directory below it (`.claude`, `.claude/skills`, ...)
   one component at a time with `mkdir` + `lstat`. A symlink or non-directory
   anywhere in the managed path fails the install before anything is staged.
   A final `realpath` check confirms the skills directory is where it should be.
3. Copy the skill (regular files and directories only, with permission bits
   preserved) into an operation-owned sibling
   `.<name>.engkit-stage-<uuid>`. Compare its content hashes with the source.
4. Publish without replacing anything:
   - **macOS:** `renamex_np(staging, dest, RENAME_EXCL)`.
   - **Linux:** `renameat2(AT_FDCWD, staging, AT_FDCWD, dest, RENAME_NOREPLACE)`.
   - **Elsewhere, or where the filesystem returns ENOSYS/EINVAL/ENOTSUP:**
     reservation protocol. `mkdir(dest)` is exclusive, so whoever creates it
     owns the reservation. Then `rename(staging, dest)`, which POSIX allows
     only onto an *empty* directory. If another writer put content into the
     reservation, the rename fails and the content is kept.
5. If the destination already exists, compare it. Identical content →
   `already installed` (exit 0). An empty directory (someone else's
   reservation, or an interrupted install) → `busy` (exit 5, retryable). A
   symlink or anything different → `conflict` (exit 3). An existing
   destination is never deleted, renamed or written to.
6. Remove only this operation's staging directory, on success and on failure.

`--target all` installs each platform independently and reports each result.
It is **not** a cross-platform transaction, and the exit code is the highest
per-target code.

## Guarantees and limitations

- Two installers racing for the same destination: exactly one publishes. The
  others report `already installed` or `conflict`. Tested with threads on both
  the native and the reservation paths.
- A destination that appears between inspection and publication is never
  replaced. This is tested by injecting a writer immediately before
  publication.
- Bundled scripts are copied as data and never executed. A test with a
  tripwire script checks this.
- **Not protected:** a hostile process that swaps a managed *parent* directory
  for a symlink between engkit's checks and its rename. Closing that window
  needs `openat`-relative operations, which Python does not expose
  portably. The threat model is accidental concurrency and pre-existing
  symlinks, not a malicious local user with write access to the project.
- On Windows (untested), the native path is unavailable, so the reservation
  protocol is used. `os.rename` onto an existing directory fails there, which
  keeps the no-replace property, but this is unverified.
