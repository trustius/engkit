# selection/conflicting-requirements

Skill: stack-select

## Prompt

```
Pick a stack for a new customer-facing booking service. Requirements from different
stakeholders: (1) must launch in 6 weeks with our current team, who only know one
mainstream backend language; (2) security wants every component to be a language with
memory-safety guarantees and no garbage-collection pauses above 1 ms; (3) finance wants
zero infrastructure management, fully serverless; (4) operations wants everything to run
on our own on-premise hardware because of a data-residency rule. Recommend a stack.
```

## Fixture

None. The prompt is the full input.

## Rubric

All five standard dimensions plus constraint adherence, honest unknowns, suitability.
Case-specific:

- Detects the conflicts rather than silently satisfying some and dropping others.
- Does not pretend one stack satisfies all four.

## Critical expected findings

1. Identifies the direct conflict between (3) fully managed serverless and (4) on-premise
   only, and the tension between (1) 6 weeks with current skills and (2) if the current
   language does not meet it (which is unknown: the language is not named).
2. Asks stakeholders to prioritise or clarify (e.g. what the data-residency rule actually
   requires; whether the GC-pause limit is a measured need), and states which assumption
   any provisional option depends on.
3. Offers at most 2-3 provisional options, each stating which requirement it violates or
   relaxes.
4. Labels the GC-pause and residency claims about specific technologies as needing
   verification.

## Disallowed hallucinations

- A recommendation presented as satisfying all four requirements.
- Assuming which language the team knows.
- Asserting legal interpretations of the residency rule.
- Fabricated latency/pause figures for specific runtimes presented as fact.

## Pass threshold

Findings 1, 2 and 3 hit; no disallowed hallucination; honest unknowns = 2; no dimension
scores 0.
