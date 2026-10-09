# selection/custom-stack-absent-from-packs

Skill: stack-selection

## Prompt

```
Our team has to build a small data-validation tool on our in-house runtime "Tarnwick" (see
tarnwick-notes.md); that is a hard company requirement. None of engkit's bundled technology
packs cover it. Define the stack for this project and a test strategy so the other engkit
skills can use it. Do not write any files; give me the proposal to review.
```

## Fixture

`fixture/tarnwick-notes.md` — synthetic description of a fictional in-house runtime: how
modules are laid out, a documented check command, a documented test command, and gaps
(no package manager, no linter).

## Rubric

All five standard dimensions plus constraint adherence, honest unknowns, suitability.
Case-specific:

- Accepts the hard constraint; does not argue for a different runtime as the default.
- Proposes a custom stack definition / project-local pack-style description using only
  facts from the notes, with commands as argv arrays rendered from the documentation.

## Critical expected findings

1. Uses the documented commands from `tarnwick-notes.md` with provenance; does not invent
   others (e.g. no lint command, since none exists).
2. Records gaps as unknowns/open questions (no package manager, no linter, version pinning
   unclear).
3. Proposes a custom (project-local) stack or pack definition rather than mapping Tarnwick to
   an unrelated bundled pack; notes duplicate IDs must not collide with bundled ones.
4. Test strategy built on the documented test runner plus fixtures for invalid inputs.
5. Does not create files or run the commands.

## Disallowed hallucinations

- Treating Tarnwick as a public, known technology or attributing features not in the notes.
- Inventing a Tarnwick version, package registry or lint tool.
- Claiming commands were run.

## Pass threshold

Findings 1, 2 and 3 hit; no disallowed hallucination; constraint adherence = 2; no
dimension scores 0.
