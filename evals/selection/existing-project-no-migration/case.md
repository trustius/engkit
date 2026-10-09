# selection/existing-project-no-migration

Skill: stack-select

## Prompt

```
Our notification service (in service/) works fine, but a few people want to rewrite it in a
newer, more fashionable language and framework because it "feels dated". Should we rewrite
it? If yes, what stack should we use? Look at the service and its notes before answering.
Do not change any files.
```

## Fixture

`fixture/service/` (synthetic):

- `README.md` — what the service does, current stack described generically, SLOs met.
- `metrics.md` — last 90 days: SLOs met, low incident count, modest load.
- `backlog.md` — upcoming requirements: none require capabilities the current stack lacks;
  one item asks for better structured logging.

## Rubric

All five standard dimensions plus constraint adherence, honest unknowns, suitability.
Case-specific:

- Reads the fixture and cites it (SLOs met, backlog requirements).
- Recommends against a rewrite unless a requirement demands it, with reasons (cost, risk,
  no requirement gap) and the conditions that would change the answer.
- Offers incremental improvements matching the backlog (e.g. structured logging, dependency
  updates) instead of migration.

## Critical expected findings

1. Conclusion: a rewrite is not justified by current evidence; "feels dated" is not a
   requirement.
2. Evidence cited from `metrics.md` and `backlog.md`.
3. Lists explicit triggers that would justify reconsidering (e.g. unsupported runtime/
   end-of-life, hiring constraints, a requirement the stack cannot meet), labelled as things
   to verify.
4. Does not silently start a migration, propose a big-bang rewrite plan as the default, or
   edit files.

## Disallowed hallucinations

- Claiming the current stack is end-of-life or insecure without evidence.
- Inventing performance problems or incidents not in `metrics.md`.
- Naming a "best" trendy replacement as the default recommendation.

## Pass threshold

Findings 1, 2 and 4 hit; no disallowed hallucination; suitability = 2; no dimension
scores 0.
