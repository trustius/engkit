# design/web-form-reuses-components

Skill: design-ui (command `/design-ui`)

Behavior under test: a spec grounded in the existing components and tokens, written as the
only file, ending with the planning hand-off.

## Prompt

```
/design-ui let admins invite teammates by email Today is 2026-10-09.
```

## Fixture

`fixture/` (synthetic project `teamboard-example`, inert data, never executed by the grader):

- `src/components/TextField.tsx`, `src/components/Button.tsx` - two existing components.
- `src/styles/tokens.css` - design tokens (colors, spacing, radius).
- `src/pages/Members.tsx` - the page the invite flow would start from; no invite exists.

## Rubric

Dimensions: factual correctness, evidence quality, false positives, unnecessary work.
Case-specific:

- Component and token claims point at real fixture paths.
- Every state is covered or has a one-line reason it does not apply.
- Copy is in a table; example emails use `example.test`.

## Critical expected findings

1. The spec is written to `docs/plans/2026-10-09-<slug>-ui-spec.md` and no other file is
   created or edited (no `.tsx`, `.css` or `package.json` change).
2. The email field and the submit button are marked `reused (src/components/TextField.tsx)`
   and `reused (src/components/Button.tsx)`; spacing and error color reference tokens in
   `src/styles/tokens.css`.
3. States loading, empty, error, success and permission denied are each covered or
   justified as not applicable (for example, loading maps to the Button `busy` prop).
4. Invalid-email and duplicate-invite error paths and a cancel path appear in the flows.
5. The final report ends with `Next step: /plan-implement <spec file>` and shows the
   spec path.

## Disallowed hallucinations

- Marking a component `reused` with a path that is not in the fixture (for example a Modal).
- Claiming an existing invite API, endpoint or role model as observed.
- Running `npm`, the dev server or any project command.
- Adding a UI library or font without asking.

## Pass threshold

All critical findings hit; no disallowed hallucination; no dimension scores 0.
