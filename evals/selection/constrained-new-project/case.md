# selection/constrained-new-project

Skill: stack-select

## Prompt

```
We are starting a new internal tool for our warehouse staff: they record stock counts on
shared laptops, and the warehouse network drops for hours at a time, so it must work fully
offline and sync later to a single office server. Team: two developers, both comfortable
with general web development, neither with mobile. Budget: no paid licences or managed
cloud services. About 15 users. Recommend a technology stack and a test strategy. We have
no code yet.
```

## Fixture

None. The prompt is the full input.

## Rubric

All five standard dimensions plus constraint adherence, honest unknowns, suitability.
Do not demand one specific answer; grade reasoning. Case-specific:

- Extracts constraints explicitly: offline-first with later sync, shared laptops (not
  phones), 2-person team skills, zero licence/cloud budget, ~15 users, single server.
- Compares 2-3 candidates with trade-offs, not a long catalogue.
- Recommends the simplest viable option and says what would change the recommendation.

## Critical expected findings

1. Constraints listed and each candidate mapped against them (especially offline operation
   and sync/conflict handling).
2. 2-3 options compared; recommendation is the simplest that meets constraints (e.g. no
   distributed/cloud infrastructure, no mobile-native stack for a laptop use case).
3. Sync conflict policy called out as a design decision/open question (two laptops counting
   the same item offline).
4. Versions, licences and maturity claims labelled as unverified unless checked against
   current sources; no fabricated version numbers.
5. Test strategy includes offline/reconnect and conflicting-edit scenarios.
6. Does not scaffold or create a project; output is a reviewable recommendation.

## Disallowed hallucinations

- Specific version numbers, release dates or licence terms stated as fact without a
  verification label.
- Recommending paid or managed cloud services as required components.
- Claiming benchmarks or adoption statistics.

## Pass threshold

Findings 1, 2, 3 and 4 hit; no disallowed hallucination; constraint adherence = 2; no
dimension scores 0.
