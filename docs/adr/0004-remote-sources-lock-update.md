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
  - environment: `GIT_TERMINAL_PROMPT=0`, `GIT_LFS_SKIP_SMUDGE=1`;
  - options on every call: `-c protocol.ext.allow=never`,
    `-c core.hooksPath=/dev/null` (so no hooks run, including the user's
    global ones), `-c advice.detachedHead=false`;
  - a timeout (default 120 s, override with `ENGKIT_GIT_TIMEOUT`);
  - git stderr is shown on failure, with `user:password@` in URLs redacted.
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
    the skill tree.
  - Built-in entries have `ref` and `commit` set to null; their content hash
    is enough to tell whether an upgrade is available.
- **Writes:** read-modify-write under an exclusive `fcntl.flock` on
  `skills.lock.json.lock`. The kernel releases it if the process dies. The
  new lock is written to a temp file and `os.replace`d. Platforms without
  `fcntl` (Windows) fail lock writes with a clear "unsupported" error rather
  than racing.
- **Recording:** an install records the entry after each target reports
  `installed` or `already installed`. If the same name is already locked from
  a different source, the result is `conflict` and nothing changes.

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
