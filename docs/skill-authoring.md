# Authoring skills

Canonical skills live in `src/engkit/skills/<name>/`. That directory is the only source;
never commit per-platform copies. Platform differences belong in
`src/engkit/platforms.py`.

## Validator contract (enforced by `engkit validate`)

- `SKILL.md` starts with YAML frontmatter containing:
  - `name`: equal to the directory name; 1–64 characters of `[a-z0-9-]`; no
    leading, trailing or doubled hyphen; must not equal a built-in skill name of
    a target platform (see `docs/compatibility.md`).
  - `description`: at most 1024 characters, covering what the skill does **and**
    when to use it. Other frontmatter keys produce a portability warning.
- `SKILL.md` has at most **120 lines**. Longer is an error.
- The body has these `##` sections, in this order:
  1. `When to use` (include out-of-scope cases)
  2. `When to ask`
  3. `Objective`
  4. `Inputs`
  5. `Workflow`
  6. `Output contract`
  7. `Guardrails`
  8. `References` (optional, last)
- Relative links resolve inside the skill directory. Symlinks and special files
  are rejected, because the installer copies regular files only.

## Shared guardrails

Every `SKILL.md` repeats these four lines verbatim under `## Guardrails`. They
are defined once as `SHARED_GUARDRAILS` in `src/engkit/validator.py`; installed
skills must be self-contained, so each skill carries its own copy and the
validator keeps the copies identical. A skill may add more specific guardrails
(for example, exact-argv approval for local commands) but must not reword these.

```markdown
- Plans: write any plan (two or more steps of future work) to `docs/plans/YYYY-MM-DD-<slug>.md` at the project root; if that name exists, use `<slug>-2.md`, then `<slug>-3.md`; never overwrite a file; report the path. If today's date is unknown, ask.
- No auto-run on servers: never run anything automatically on a server environment (prod, staging, dev, test), including its databases, clusters, queues and cloud accounts. Never run a state-changing action there; write the exact steps for the user. A read-only command (status, logs) runs only after the user says yes to that exact command. If unsure whether a target is a server environment, treat it as one and ask.
- Sensitive data: never print, copy or store keys, tokens, passwords, connection strings, PII or PHI, whether in chat, plans, memory or files. Refer to them by location (`file:line`) and write `[REDACTED]`. Use synthetic data in examples.
- Incremental: work in small steps; after each step, check the result and report it; stop at the first failed check and ask.
```

## Content rules

- **When to ask.** List the cases where the agent must stop and ask the user
  instead of guessing: missing inputs, contradictions, ambiguous targets, and
  any step that would change state.
- **Memory hook.** At task start, read `.engkit/memory/INDEX.md` if it exists.
  Open only the entries that look relevant. Verify each entry against current
  code before relying on it. If the file does not exist, continue without it.
  Do not create or edit memory unless the skill's workflow says so; memory
  writes go through `memory-save`.
- **No implicit authority.** No skill edits files without an explicit user request.
  `implement-plan` edits files only after the user's session approval of the slice
  and its commands. No skill authorizes production access or destructive actions.
  A documented command is neither permission to run it nor evidence that it passes.
- **Design-spec file.** `design-ui` writes one file, a UI spec at
  `docs/plans/YYYY-MM-DD-<slug>-ui-spec.md` (collision suffix, never overwritten), and
  edits nothing else. `plan-implement` reads a spec and never edits it.
- **Plan-file progress exception.** `implement-plan` may update only the
  `## Progress` section of the plan it is implementing, and only after the
  approval above. This is not plan writing: the Plans rule still forbids
  overwriting plan files, and no other part of a plan may be edited.
- **Facts versus assumptions.** Output contracts label every claim as
  **verified fact** (checked in this session, with the source), **plausible
  hypothesis** (consistent with the evidence, not checked) or **untested
  assumption** (taken on trust).
- **Length and depth.** Keep the body short. Put depth in `references/` and say
  when to load each reference.
- **Technology names** appear only in clearly labelled optional examples or
  references. Examples are synthetic: use `example.test` and placeholders such as
  `PLACEHOLDER_SECRET`.

## Output template

Use this shape in `## Output contract`. Adapt the headings to the skill, but keep
the three labels:

```markdown
## Output

**Verified fact**
- <claim> (source: <file:line or command and its result>)

**Plausible hypothesis**
- <claim> (basis: <evidence>; not checked: <what would check it>)

**Untested assumption**
- <claim> (why it is assumed)

**Questions for the user**
- <question, only when a When to ask case applies>
```

## Evals

- Trigger evals: one file per skill in `evals/triggers/<name>.md`. They list
  prompts that should and should not activate the skill.
- Scenario evals: add at least two synthetic cases per skill under
  `evals/<area>/<case-id>/` (see `evals/README.md`). Results are recorded only
  from real runs; a case with no run stays `not-run`.

## Workflow

```bash
.venv/bin/engkit validate my-skill                           # lint one skill
.venv/bin/python -m unittest tests.test_validator            # validator tests
.venv/bin/engkit install my-skill --target all --project-dir /tmp/demo   # try it in a scratch project
```

Use a scratch directory for the last command, not a real project. Add a test in
`tests/` for each new validator rule.
