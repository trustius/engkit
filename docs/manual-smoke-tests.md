# Manual platform smoke tests

These checks need a real agent session, so automated tests cannot stand in
for them. Record results in the table at the end. **Do not mark a check
passed unless you ran it.**

Prerequisites: a scratch directory outside any real repository and a
throwaway project. Use `--project-dir`. Do not use `--global` unless you
intend to change your real home directory.

## 1. Claude Code: install and invoke

```bash
mkdir -p /tmp/engkit-smoke/claude && cd /tmp/engkit-smoke/claude && git init -q
engkit install systematic-debugging --target claude --project-dir .
engkit doctor --target claude --project-dir . --project-only
claude    # then ask: "What skills are available?" and
          # "Use the systematic-debugging skill: tests/test_x fails with KeyError 'id' (synthetic)."
```

Expected: the skill is listed and its output separates verified fact,
plausible hypothesis and untested assumption.

## 2. Codex: install and invoke

```bash
mkdir -p /tmp/engkit-smoke/codex && cd /tmp/engkit-smoke/codex && git init -q
engkit install code-review --target codex --project-dir .
codex     # ask Codex to list skills, then to review a small synthetic diff with the code-review skill
```

Also confirm whether Codex reads user skills from `~/.codex/skills` or
`~/.agents/skills` (open question in `compatibility.md`).

## 3. Coexistence with instruction files

Create `CLAUDE.md` and `AGENTS.md` with a sentinel line. Run `install`,
`project generate --target all` and `doctor`, then confirm both files are
byte-for-byte unchanged (`shasum` before and after).

## 4. Removing the example project

Delete `/tmp/engkit-smoke/*`. Confirm that `~/.claude/skills` and
`~/.codex/skills` are unchanged.

## 5. Context consumption (after M6C)

Use a copy of `evals/discovery/mixed-monorepo/fixture`:

```bash
engkit install systematic-debugging --target all --project-dir .
engkit project generate --project-dir . --target all
```

Ask each agent to debug a failure in `tools/cli`. Expected: it reads
`components/tools-cli.md`, quotes the `tools/cli` command and does not
mention the other components' commands. Repeat with:

- (a) `.engkit/generated` deleted: generic fallback;
- (b) a new `libs/extra/Cargo.toml` added: `doctor` reports stale, and the
  agent says so;
- (c) `engkit` removed from PATH: freshness reported as unverified;
- (d) a task touching `apps/web` and `libs/core`: commands are kept separate,
  and the `apps/web` package-manager ambiguity is reported rather than
  resolved.

## Results

| Date | Check | Platform + version | OS | Outcome | Notes |
|---|---|---|---|---|---|
| 2026-10-09 | 1 | Claude Code 2.1.295 | macOS (Darwin 25.5) | pending | Not run: needs an interactive agent session and model access |
| 2026-10-09 | 2 | Codex CLI 0.144.1 | macOS (Darwin 25.5) | pending | Not run: same reason |
| 2026-10-09 | 3 | n/a (CLI only) | macOS | pending | Automated equivalent: tests/test_cli.py asserts existing CLAUDE.md/AGENTS.md are unchanged after install, generate, replace and doctor |
| 2026-10-09 | 4 | both | macOS | pending | |
| 2026-10-09 | 5 | both | macOS | pending | Fixture-level checks automated in tests/test_generation.py; agent-level behavior unverified |
