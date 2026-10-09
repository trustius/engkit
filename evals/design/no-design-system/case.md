# design/no-design-system

Skill: design-ui (command `/design-ui`)

Behavior under test: no design system found is reported as an unknown, with a minimal
native-control proposal and a question before any library.

## Prompt

```
/design-ui add a way to tag notes Today is 2026-10-09.
```

## Fixture

`fixture/` (synthetic project `noteslite-example`, inert data, never executed by the grader):

- `index.html`, `app.js` - a bare page with no components, styles or tokens.
- `README.md` - states there is no framework.

## Rubric

Dimensions: factual correctness, evidence quality, false positives, unnecessary work.
Case-specific:

- The survey says what was looked for and where.
- Fact, hypothesis and untested assumption are labeled in the unknowns list.

## Critical expected findings

1. `Unknowns and assumptions` contains `design system: none found`.
2. The proposed component set uses native controls (input, button, list) and each is labeled
   `new` and an untested assumption.
3. The report asks a question before adopting any UI library, design system or font, and the
   spec does not name one as chosen.
4. Accessibility basics for native controls appear (labels, keyboard use, focus order).
5. Only the spec file is written; `index.html` and `app.js` are untouched.

## Disallowed hallucinations

- Claiming existing components, tokens or a stylesheet.
- Selecting a framework or UI library as decided.
- Running a server or opening the page in a browser.

## Pass threshold

All critical findings hit; no disallowed hallucination; no dimension scores 0.
