# ADR 0004: Skills from git sources, lockfile, update and uninstall

- Status: accepted (ENHANCEMENT_PLAN P4). Decisions Q2–Q4 confirmed by the user on 2026-10-09.

## Commands

```bash
engkit list --source <git-url> [--ref REF] [--path DIR]
engkit install <name> --target T [--project-dir P | --global]                  # built-in
engkit install --source <git-url> [--ref REF] [--path DIR] --skill a [--skill b] --target T [--yes]
engkit update [<name>] [--target T] [--project-dir P | --global] [--yes]
engkit uninstall <name> --target T [--project-dir P | --global]
```

Only `list --source`, `install --source` and `update` of a git-sourced entry
use the network. `validate`, `doctor`, `memory`, built-in `install` and
`uninstall` stay offline.

## Fetching (`sources.py`)

- **Allowed URLs:** `https://`, `ssh://`, scp-style `user@host:path` and
  `file://` (`file://` is used for tests and local mirrors). Anything else is
  rejected before git runs, including `ext::`, `fd::`, other `transport::`
  forms, bare paths and values starting with `-`. `--ref` must match
  `[A-Za-z0-9][A-Za-z0-9._/-]*`, must not contain `..` and must not start with
  `-`. `--path` must be a safe relative path.
- **Fetch sequence:** run the system `git` via `subprocess` with an argv list
  (never a shell), into a fresh `tempfile.mkdtemp()` directory that is deleted
  in `finally`:
  1. `git init -q`
  2. `git fetch --depth 1 --no-recurse-submodules --no-tags -- <url> <ref or HEAD>`
  3. `git checkout -q FETCH_HEAD`
  4. `git rev-parse HEAD` (the commit recorded in the lock)

  The plan suggested `clone --depth 1`; init + fetch gives the same shallow,
  submodule-free result and also accepts a commit SHA, which a lock-pinned
  reinstall needs.
- **Hardening:**
  - environment: every `GIT_*` variable is dropped, then only `GIT_SSH`,
    `GIT_SSH_COMMAND`, `GIT_SSL_CAINFO` and `GIT_SSL_CAPATH` are passed through
    (proxy, `SSL_CERT_*`, `HOME` and `PATH` are not `GIT_*` and stay).
    `GIT_TERMINAL_PROMPT=0`, `GIT_LFS_SKIP_SMUDGE=1`, empty `GIT_ASKPASS` and
    `SSH_ASKPASS`, and `ssh -o BatchMode=yes` unless the user set an ssh command;
  - options on every call: `--git-dir` and `--work-tree` pointing at the temp
    checkout (an ambient `GIT_DIR` can never redirect a write),
    `-c protocol.ext.allow=never`, `-c core.hooksPath=/dev/null` (so no hooks
    run, including the user's global ones), `-c advice.detachedHead=false`,
    `-c submodule.recurse=false`, `-c core.fsmonitor=false`;
  - git runs in its own session; a timeout (default 120 s, override with a
    positive `ENGKIT_GIT_TIMEOUT`) kills the whole process group;
  - URLs with a password, an https user, a query string or a fragment are
    rejected (use a git credential helper or ssh); git stderr is shown on
    failure with any userinfo removed;
  - fetched text is escaped (`\xNN`) before it is printed, validation rejects
    control characters in file names, and a skill may have at most 500 files,
    1 MiB per file and 10 MiB in total.
- **Skill location:** `--path DIR` when given. Otherwise `skills/` if it
  exists, else the repository root.
- **No git:** commands that need git fail with a clear message. Tests skip.

## Untrusted content

- Remote skills go through the same validator as built-in ones (names,
  frontmatter, sections, references, escaping symlinks). The copier refuses
  every symlink and special file.
- Files are never executed, imported or sourced.
- **Preview (Q3):** without `--yes`, `install --source` and a remote `update`
  print the URL, ref, resolved commit, each skill's files with sizes, and a
  separate list of risky files (executable bit set, or under `scripts/`).
  Validation results come last, followed by "nothing installed; re-run with
  `--yes`". The exit code is 0 and the status is `preview`. The `--yes` run
  fetches again and prints the commit it actually installs; pin `--ref <sha>`
  to guarantee the same content.

## Lockfile (`lockfile.py`)

- **Location:** `<project>/.engkit/skills.lock.json` (meant to be committed,
  Q2) and `~/.engkit/skills.lock.json` for `--global`.
- **Format:**

  ```json
  {"lock_version": 1,
   "skills": {"<name>": {"source": "builtin" | "<url>", "ref": "<ref>" | null, "path": "<dir>" | null,
                         "commit": "<sha>" | null, "content_sha256": "<digest>", "targets": ["claude", "codex"]}}}
  ```

  - `content_sha256` is the sha256 of the sorted `path\0filehash\n` lines of
    the skill tree. A file hash carries a `+x` suffix when the executable bit
    is set (no other mode bits, to avoid umask noise).
  - Optional `target_digests` maps a target id to the digest of that target's
    copy. It exists only after a partial update (some targets updated, others
    not) and overrides `content_sha256` for that target in the pristine checks
    of update and uninstall. Keys must be a subset of `targets`, values 64 hex
    digits. It is removed once all targets are current or a target is
    uninstalled.
  - Built-in entries have `ref` and `commit` set to null; their content hash
    is enough to tell whether an upgrade is available.
- **Writes:** read-modify-write under an exclusive `fcntl.flock` on
  `skills.lock.json.lock`. The kernel releases it if the process dies. The
  new lock is written to a temp file and `os.replace`d. Platforms without
  `fcntl` (Windows) fail lock writes with a clear "unsupported" error rather
  than racing.
- **Recording:** an install records the entry after each target reports
  `installed` or `already installed`. If the same name is already locked from
  a different source, the result is `conflict` and nothing changes; the check
  is repeated inside the lock transaction. An identical but unmanaged
  destination is adopted into the lock as `already installed`.

## Update and uninstall (`installer.py`)

- **Update replaces only a pristine install:** an installed copy is replaced
  only when its content hash equals the lock's `content_sha256`, meaning the
  user has not edited it. Otherwise the result is `conflict` and the copy is
  untouched. A missing lock entry gives "not managed by engkit".
- **Update sequence:**
  1. Stage the new tree in `<root>/.engkit/staging/<tx>/new`. Staging is
     outside the skills directory, so agents never see it as a skill.
  2. Verify the staged copy.
  3. Re-check the installed hash.
  4. `rename(dest → staging/<tx>/old)`.
  5. No-replace rename `new → dest`.
  6. Verify, then delete `old` and update the lock.

  After step 4 the moved copy is hashed again; if it no longer equals the lock
  digest it is renamed back (or kept in staging with its path reported) and
  the result is `conflict`. Any failure after step 4, including an interrupt,
  restores `old` before staging is deleted. `update --target X` is refused
  when other targets of the entry would stay on the old content. A failed
  fetch of one skill is reported for that skill and the others continue.

  If step 5 or 6 fails, rename `old` back. If that also fails, because
  something took the path, `old` is kept and its location reported. A brief
  window exists where `dest` is absent; this is documented.
- **Uninstall:** same hash check. Move `dest → staging/<tx>/removed`, delete
  it, and drop the target from the lock (dropping the entry when no targets
  remain).
- **Remote updates:** re-fetch `source` at the recorded `ref` (not the old
  commit). The preview shows `old commit → new commit` and needs `--yes`.
  Built-in updates compare against the bundled canonical skill and need no
  confirmation.

## Residual risks

- Malicious skill *text* (prompt injection) cannot be detected
  mechanically. The preview and the user's review are the control.
- Shallow fetch by SHA depends on the server allowing it. Hosting providers
  generally do, and `file://` does.
- A local attacker who swaps managed directories mid-operation is out of
  scope (see ADR 0002).
- A fetched repository's `.gitattributes` can invoke filter drivers that the
  user already defined in their own global git config during checkout (LFS
  smudge is disabled). engkit defines no filters itself. Full mitigation would
  need `git archive` extraction or git >= 2.40 attribute-source control.
