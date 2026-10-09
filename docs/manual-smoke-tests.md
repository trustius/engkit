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

**Release blocker:** Codex user scope is `~/.agents/skills` (official docs), but
the 0.144.1 binary only mentions `~/.codex/skills`. Confirm that Codex
0.144.1 reads it (open question in `compatibility.md`). Do this with `--global`
only if you accept that it writes to your home directory.

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

## 6. Slash commands (Claude Code)

Use a copy of a synthetic fixture, so no real project is touched.

```bash
mkdir -p /tmp/engkit-smoke && rm -rf /tmp/engkit-smoke/slash-claude
cp -R /absolute/path/to/engkit/evals/discovery/mixed-monorepo/fixture /tmp/engkit-smoke/slash-claude
cd /tmp/engkit-smoke/slash-claude && git init -q && git add -A \
  && git -c user.email=smoke@example.test -c user.name=smoke commit -qm "baseline"
$ENGKIT init --project-dir . --target claude
claude --version     # record the version
claude               # then the steps below
```

1. Type `/`. Expected: `/engineering-onboard`, `/plan-implement`, `/implement-plan`,
   `/change-review`, `/bug-investigate`, `/stack-select` and `/memory-save` are
   listed. No old name appears.
2. Run `/engineering-onboard`. Expected: it maps the fixture and writes only
   under `.engkit/memory/`. Run `git status` before and after. Expected: no
   other file changed, and `CLAUDE.md` and `AGENTS.md` are not edited.
3. Change one file in the fixture by hand (`echo "synthetic change" >> <file>`),
   then run `/change-review`. Expected: it reviews the uncommitted change against
   HEAD, separates verified fact, hypothesis and assumption, and edits nothing.

Record the Claude Code version, the model, and the result of each step in the
results table.

## 7. Slash commands (Codex)

Same fixture approach, in a separate copy.

```bash
rm -rf /tmp/engkit-smoke/slash-codex
cp -R /absolute/path/to/engkit/evals/discovery/mixed-monorepo/fixture /tmp/engkit-smoke/slash-codex
cd /tmp/engkit-smoke/slash-codex && git init -q && git add -A \
  && git -c user.email=smoke@example.test -c user.name=smoke commit -qm "baseline"
$ENGKIT init --project-dir . --target codex     # installs to .agents/skills/
codex --version      # record the version
codex                # then the steps below
```

1. Type `/skills` or `$`. Expected: the same seven commands are listed, including
   `$implement-plan`.
2. Run `$engineering-onboard`, then `$change-review` after a synthetic edit, as
   in section 6. Expected results are the same.
3. Optional: run `$change-review synthetic-argument` and record whether the
   argument reaches the command. This is the pending question in
   `compatibility.md`. Record the answer either way.

Record the Codex CLI version, the model, and the result of each step.

## 8. Plan → implement → review (Claude Code)

A synthetic two-slice change in a throwaway Python project. Slice 1 adds
`multiply`, slice 2 adds `square`, and both are verified by one command.

```bash
rm -rf /tmp/engkit-smoke/plan-claude && mkdir -p /tmp/engkit-smoke/plan-claude/tests
cd /tmp/engkit-smoke/plan-claude && git init -q
printf 'def add(a, b):\n    return a + b\n' > calc.py
printf 'import unittest\nfrom calc import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n' > tests/test_calc.py
$ENGKIT init --project-dir . --target claude
claude --version     # record the version
claude               # then the steps below
```

1. Run `/plan-implement add multiply and square to calc.py in two slices`. Expected:
   a plan is written to `docs/plans/YYYY-MM-DD-<slug>.md`, each slice has a
   verification that is a command (argv and cwd) or a named manual check, and the
   next step is `/implement-plan docs/plans/<file>`. Then, in a second shell, run
   `git add -A && git -c user.email=smoke@example.test -c user.name=smoke commit -qm baseline`
   so the preflight starts from a clean tree (`docs/plans/` is gitignored only in
   engkit's own repository).
2. Run `/implement-plan docs/plans/<file>` (slice 1). Expected, in this order:
   - Before any edit, an approval request shows slice 1, the files it will change
     (the files the plan's slice 1 names, for example `calc.py` and `tests/test_calc.py`,
     plus the plan's `## Progress`), and the
     verification commands of both slices as argv and cwd. Check `git status` in
     the second shell now: expected clean. If a file changed before the request
     appeared, record the check as failed.
   - Answer `yes`. Then `git status` shows only `calc.py`, `tests/test_calc.py`
     and the plan file as changed. Nothing else changed.
   - The approved command runs (`python3 -m unittest discover -s tests`, cwd the
     project root) and passes. The plan's `## Progress` has a `done` row for slice 1.
   - It suggests a commit message and stops without starting slice 2.
3. Reply `continue`. Expected: slice 2 is shown with its files, its edits stay
   inside those files, and the command approved in step 2 runs again without a new
   yes. Its Progress row is `done`, and it stops again.
4. Run `/change-review`. Expected: it reviews the uncommitted changes against HEAD,
   separates verified fact, hypothesis and assumption, and edits nothing. Run
   `git status` before and after: no change.

Record the Claude Code version, the model, and the result of each step in the
results table.

## 9. Plan → implement → review (Codex)

Same synthetic project in a separate copy, with `$` commands.

```bash
rm -rf /tmp/engkit-smoke/plan-codex && mkdir -p /tmp/engkit-smoke/plan-codex/tests
cd /tmp/engkit-smoke/plan-codex && git init -q
printf 'def add(a, b):\n    return a + b\n' > calc.py
printf 'import unittest\nfrom calc import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n' > tests/test_calc.py
$ENGKIT init --project-dir . --target codex     # installs to .agents/skills/
codex --version      # record the version
codex                # then the steps below
```

1. Run `$plan-implement add multiply and square to calc.py in two slices`, then commit
   the baseline as in section 8, step 1.
2. Run `$implement-plan docs/plans/<file>`. Expected: the same approval request,
   edits and stop as section 8, step 2. The plan path is an argument, and Codex's
   argument passing is pending (`compatibility.md`). If the path does not reach the
   command, the expected result is the list of incomplete plans and a question
   about which one. Record which behavior occurred.
3. Reply `continue`, then run `$change-review`. Expected: the same results as
   section 8, steps 3 and 4.

Record the Codex CLI version, the model, and the result of each step.

## 10. Cleanup

Delete `/tmp/engkit-smoke/*`. Confirm that `~/.claude/skills`, `~/.agents/skills`,
`~/.codex/skills` (legacy) and `~/.engkit` are unchanged compared with before
the run.

## Results

Every outcome is `pending`. No check has been run in a live session yet.

| Date | Check | Platform + version | OS | Outcome | Notes |
|---|---|---|---|---|---|
| 2026-10-09 | 1 | Claude Code 2.1.295 | macOS (Darwin 25.5) | pending | Not run: needs an interactive agent session and model access |
| 2026-10-09 | 2 | Codex CLI 0.144.1 | macOS (Darwin 25.5) | pending | Not run: needs an interactive agent session. The preview and install steps can run without an agent |
| 2026-10-09 | 3 | engkit CLI only | macOS | pending | Not run as a manual check. Unit tests use temp directories only; they do not replace this run |
| 2026-10-09 | 4 | Claude Code 2.1.295 and Codex CLI 0.144.1 | macOS | pending | Not run: needs two fresh agent sessions |
| 2026-10-09 | 5 | engkit CLI only | macOS | pending | Not run. Agent behavior with the sentinel files is unverified |
| 2026-10-09 | 6 (slash, Claude Code) | Claude Code 2.1.295 (record actual) | macOS | pending | Not run: `/` list, `/engineering-onboard`, `/change-review`. Record model |
| 2026-10-09 | 7 (slash, Codex) | Codex CLI 0.144.1 (record actual) | macOS | pending | Not run: `/skills`, `$engineering-onboard`, `$change-review`, argument test. Record model |
| 2026-10-09 | 8 (plan → implement → review, Claude Code) | Claude Code 2.1.295 (record actual) | macOS | pending | Not run: needs an interactive session and model access. Record model |
| 2026-10-09 | 9 (plan → implement → review, Codex) | Codex CLI 0.144.1 (record actual) | macOS | pending | Not run: needs an interactive session. Record whether the plan path reaches `$implement-plan` |
| 2026-10-09 | 10 | engkit CLI only | macOS | pending | Not run |
