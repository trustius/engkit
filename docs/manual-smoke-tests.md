# Manual platform smoke tests

These checks need a real agent session or a manual walk-through, so automated
tests cannot stand in for them. Record results in the table at the end. **Do not
mark a check passed unless you ran it.**

Prerequisites: a scratch directory outside any real repository and a throwaway
project. Use `--project-dir`. Do not use `--global` unless you intend to change
your real home directory. Set `ENGKIT=/absolute/path/to/engkit/.venv/bin/engkit`
and use it below.

## 1. Built-in install and Claude Code invocation

```bash
mkdir -p /tmp/engkit-smoke/claude && cd /tmp/engkit-smoke/claude && git init -q
$ENGKIT install bug-investigate --target claude --project-dir .
$ENGKIT doctor --target claude --project-dir . --project-only
claude    # then ask: "What skills are available?" and
          # "Use the bug-investigate skill: tests/test_x fails with KeyError 'id' (synthetic)."
```

Expected: the skill is listed, and its answer separates verified fact,
plausible hypothesis and untested assumption.

## 2. Remote install (file:// git source) and Codex invocation

Build a synthetic source repository. It is a local file, so no network is used.

```bash
mkdir -p /tmp/engkit-smoke/source/skills && cd /tmp/engkit-smoke/source
cp -R /absolute/path/to/engkit/src/engkit/skills/change-review skills/
git init -q && git add -A && git -c user.email=smoke@example.test -c user.name=smoke commit -qm "baseline"

mkdir -p /tmp/engkit-smoke/codex && cd /tmp/engkit-smoke/codex && git init -q
$ENGKIT install --source file:///tmp/engkit-smoke/source --path skills \
  --skill change-review --target codex --project-dir .          # preview only; writes nothing
$ENGKIT install --source file:///tmp/engkit-smoke/source --path skills \
  --skill change-review --target codex --project-dir . --yes    # installs
codex     # ask Codex to list skills, then to review a small synthetic diff with change-review
```

Expected: the preview lists the commit, the file list and any executable files,
and writes nothing. The `--yes` run writes `.agents/skills/change-review/` and
`.engkit/skills.lock.json`. Codex lists the skill and uses it.

Also confirm whether Codex reads user skills from `~/.codex/skills` or
`~/.agents/skills` (open question in `compatibility.md`). Do this with
`--global` only if you accept that it writes to your home directory.

## 3. Update and uninstall

```bash
cd /tmp/engkit-smoke/codex
echo "synthetic note" >> .agents/skills/change-review/SKILL.md   # simulate a local edit
$ENGKIT update change-review --target codex --project-dir .       # expect: conflict, file untouched
# restore the file from the source, then check that update is a no-op:
cd /tmp/engkit-smoke/source && echo "synthetic change" >> skills/change-review/SKILL.md \
  && git -c user.email=smoke@example.test -c user.name=smoke commit -qam "synthetic change"
cd /tmp/engkit-smoke/codex
$ENGKIT update change-review --target codex --project-dir .       # preview: old -> new commit
$ENGKIT update change-review --target codex --project-dir . --yes # applies the new commit
$ENGKIT uninstall change-review --target codex --project-dir .    # removes the unmodified install
```

Expected: a modified install is a conflict and is left as is; a git-sourced
update shows the old and new commit and needs `--yes`; uninstall removes only an
unmodified, lock-managed install.

## 4. Project memory with an agent

```bash
cd /tmp/engkit-smoke/claude
$ENGKIT memory init --project-dir .      # prints the CLAUDE.md and AGENTS.md snippets; add them yourself
$ENGKIT memory validate --project-dir .
$ENGKIT doctor --target all --project-dir .
```

Create one synthetic entry in `.engkit/memory/` by hand (or ask the agent to
record one with `memory-save`), then update `INDEX.md` to list it and run
`memory validate` again. In a fresh Claude Code session and a fresh Codex
session, ask: "What does the project memory say about the test runner?"

Expected: each agent reads `.engkit/memory/INDEX.md`, opens only the relevant
entry, and reports the entry as a claim to verify against the code. Claude Code
auto memory must not have the same fact recorded (see `CLAUDE.md`).

## 5. Coexistence with instruction files

Create `CLAUDE.md` and `AGENTS.md` in the scratch project with a sentinel line.
Record their checksums, then run `memory init`, `install`, `update`, `uninstall`
and `doctor`. Compare the checksums afterwards.

```bash
cd /tmp/engkit-smoke/claude
printf 'SENTINEL-CLAUDE\n' > CLAUDE.md && printf 'SENTINEL-AGENTS\n' > AGENTS.md
shasum CLAUDE.md AGENTS.md > before.sum
# ...run the commands from sections 1-4 here...
shasum -c before.sum
```

Expected: both files are byte-for-byte unchanged. Only the snippets printed by
`memory init` are for you to add.

## 6. Cleanup

Delete `/tmp/engkit-smoke/*`. Confirm that `~/.claude/skills`, `~/.codex/skills`,
`~/.agents/skills` and `~/.engkit` are unchanged compared with before the run.

## Results

Every outcome is `pending`. No check has been run in a live session yet.

| Date | Check | Platform + version | OS | Outcome | Notes |
|---|---|---|---|---|---|
| 2026-10-09 | 1 | Claude Code 2.1.295 | macOS (Darwin 25.5) | pending | Not run: needs an interactive agent session and model access |
| 2026-10-09 | 2 | Codex CLI 0.144.1 | macOS (Darwin 25.5) | pending | Not run: needs an interactive agent session. The preview and install steps can run without an agent |
| 2026-10-09 | 3 | engkit CLI only | macOS | pending | Not run as a manual check. Unit tests use temp directories only; they do not replace this run |
| 2026-10-09 | 4 | Claude Code 2.1.295 and Codex CLI 0.144.1 | macOS | pending | Not run: needs two fresh agent sessions |
| 2026-10-09 | 5 | engkit CLI only | macOS | pending | Not run. Agent behavior with the sentinel files is unverified |
| 2026-10-09 | 6 | engkit CLI only | macOS | pending | Not run |
