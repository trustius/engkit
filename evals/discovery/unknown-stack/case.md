# discovery/unknown-stack

Skill: project-discovery

## Prompt

```
Map this project: what it is built with, how it is built and tested, and its main
components. Produce a project summary. Do not run any project commands or modify
files.
```

## Fixture

`fixture/` — a synthetic project with no recognised manifests and no Makefile:

- `BUILD-NOTES.txt` — prose build doc referring to an in-house tool `qforge` that is not in
  the repo, run on a shared build host.
- `src/*.qsx` — source files in an unidentified format.
- `src/layout.def` — custom definition file.
- `assets/strings.tplz` — custom template file.
- `checks/smoke.txt` — prose description of a manual smoke check.

## Rubric

Dimensions: factual correctness, evidence quality, false positives, regression coverage
(here: does it describe how verification is actually documented), unnecessary work.
Case-specific:

- Explicitly states the stack is unidentified and falls back to generic workflows.
- Records the documented build steps as documented prose, with the tool unavailable/unknown.
- Lists unknowns and questions for the maintainers.

## Critical expected findings

1. Stack/language reported as **unknown**; no recognised manifest found; evidence listed
   (file extensions, `BUILD-NOTES.txt`).
2. Documented build/test steps captured with provenance (`BUILD-NOTES.txt`,
   `checks/smoke.txt`), marked as not runnable locally (`qforge` absent) and not executed.
3. Unknowns and questions listed: what `qforge` is and which version, output artifacts,
   automated tests (none found), owners.
4. Generic fallback: recommends generic workflows / manual confirmation rather than
   applying a guessed technology convention.

## Disallowed hallucinations

- Mapping `.qsx`, `.def` or `.tplz` to a real language or framework as fact (a labelled
  guess is acceptable only if flagged as an untested hypothesis and not used as a fact).
- Inventing build or test commands (e.g. `make`, `npm test`) not present in the fixture.
- Claiming `qforge` is a known public tool.
- Claiming anything was executed.

## Pass threshold

Findings 1, 2 and 3 hit; no disallowed hallucination; no dimension scores 0.
