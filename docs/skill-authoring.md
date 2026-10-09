# Authoring skills

Canonical skills live in `skills/<name>/`. That directory is the only
source; never commit per-platform copies.

## Checklist (enforced by `engkit validate`)

- `SKILL.md` starts with YAML frontmatter containing `name` (equal to the
  directory name, 1–64 characters of `[a-z0-9-]`, no leading, trailing or
  doubled hyphen) and `description` (1–1024 characters, covering what the
  skill does **and** when to use it). Other keys produce a portability
  warning.
- The body has these `##` sections, in order: `When to use` (including
  out-of-scope cases), `Objective`, `Inputs`, `Project context (optional)`,
  `Workflow`, `Output contract`, `Guardrails`. An optional `## References`
  section goes last.
- Relative links must resolve inside the skill directory. No symlinks (the
  installer copies regular files only, so even an internal symlink fails
  validation), and no special files.
- Keep the body short (warning above 500 lines). Put depth in `references/`
  and say when to load each reference.

## Content rules

- Output contracts distinguish **verified fact**, **plausible hypothesis**
  and **untested assumption**.
- No skill implicitly authorizes edits, production access or destructive
  actions. A documented command is neither permission to run it nor evidence
  that it passes.
- Technology names appear only in clearly labelled optional examples,
  references or packs. Examples are synthetic.
- The `Project context (optional)` section implements the context hook. It
  locates `.engkit/generated/PROJECT_CONTEXT.md` in the target project,
  checks freshness with `engkit doctor --target all --project-dir <root>`, or
  checks `.engkit/generation-transaction.json` and verifies facts against
  files when the CLI is unavailable. It selects the deepest containing
  component root, loads only the relevant files and falls back to the
  generic workflow. It never regenerates implicitly.
  `tests/test_validator.py` checks the key phrases.

## Workflow

```bash
engkit validate my-skill
.venv/bin/python -m unittest tests.test_validator
engkit install my-skill --target all --project-dir /tmp/demo   # try it in a scratch project
```

Add at least two synthetic eval cases under `evals/` (see `evals/README.md`).
