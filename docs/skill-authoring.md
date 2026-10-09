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

## Content rules

- **When to ask.** List the cases where the agent must stop and ask the user
  instead of guessing: missing inputs, contradictions, ambiguous targets, and
  any step that would change state.
- **Memory hook.** At task start, read `.engkit/memory/INDEX.md` if it exists.
  Open only the entries that look relevant. Verify each entry against current
  code before relying on it. If the file does not exist, continue without it.
  Do not create or edit memory unless the skill's workflow says so; memory
  writes go through `memory-save`.
- **No implicit authority.** No skill authorizes edits, production access or
  destructive actions. A documented command is neither permission to run it nor
  evidence that it passes.
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
