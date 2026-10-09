---
name: stack-selection
description: Turn product requirements and constraints into two or three viable technology-stack options with trade-offs and a test strategy, and optionally record the choice as a project memory decision. Use when starting a new project or component, or when asked to compare stacks against stated requirements.
---

# Stack selection

## When to use
- Starting a new project or a component that has no established stack.
- The user asks to compare stacks for stated requirements.
- An existing project has requirements its current stack demonstrably cannot meet.
- Out of scope: describing an existing stack (use `project-discovery`); migrating a working
  project without a demanding requirement; scaffolding, installing, provisioning or deploying;
  picking a library for one scoped task (use `implementation-planning`).

## When to ask
- Requirements conflict (for example fully managed hosting vs on-premise only): name the
  conflict and ask which requirement wins.
- A hard constraint is missing and would change the choice (team skills, budget, hosting,
  compliance).
- The project already has a working stack: ask whether a change is really wanted.
- You want to record the decision in memory or any file: ask for consent.
- A version or compatibility fact is needed and there is no network permission: ask.

## Objective
A defensible choice among a few viable options, with reasons, assumptions and trade-offs
explicit, plus a test strategy.

## Inputs
- Product type, workload and scale, team experience, budget.
- Operational, security and compliance constraints, integrations, deployment environment.
- For an existing project: its current stack, which is a constraint, not a defect.
- Project memory (optional): if `.engkit/memory/INDEX.md` exists in the target project, read
  it and open only entries relevant to the task. Verify each against current code before
  relying on it, and report which entries were used. If absent, proceed normally. Write memory
  only with the user's consent, following the project-memory format.

## Workflow
1. List the stated requirements and constraints, marking each hard or soft.
2. If memory exists, read INDEX.md and open `decision` and `context` entries.
3. If a working stack already exists and no requirement demands change, say migration is
   unnecessary, then stop or limit the choice to the new component.
4. Find conflicts between requirements. If any exist, ask which wins before recommending.
5. List the questions whose answers would change the choice. Ask only those; record every
   other gap as an untested assumption.
6. Write two or three options, simplest viable first. Give each a one-line summary.
7. Score each option against each requirement as meets, relaxes or violates, plus team
   familiarity, operational burden, cost, maturity, security and exit cost.
8. Mark every version, price and benchmark as unverified unless you read official
   documentation this session with network permission. Never invent them.
9. Recommend one option, with reasons and what evidence would change the recommendation.
10. Write a test strategy: levels, tool categories, and the first three tests.
11. If the user consented, write one `decision` memory entry (choice and reasons, status
    `assumption` or `hypothesis` until validated) and add an INDEX.md line.

## Output contract
Fill in this template.

```
Requirements: <id | requirement | hard|soft>   Conflicts: <list or none>
Memory used: <entry - verified | stale | unverifiable> or none
Options:
- A: <summary> | meets/relaxes/violates per requirement | trade-offs | risks
- B: ...
Recommendation: <option> because <reasons>; would change if <evidence>
Claims:
- verified fact: <from provided requirements or docs read now>
- plausible hypothesis: <reasoned judgment>
- untested assumption: <taken as given>
Versions: unverified (no network) or verified with <source>
Test strategy: <levels, tools, first tests>
Memory written: <entry> or none (consent not given)
Commands run: none
```

## Guardrails
- Never migrate or rewrite an existing project silently; a recommendation is not authorization.
- No file writes unless the user asked or consented.
- No installs, scaffolding, provisioning, deployment, production access or destructive actions.
- No network lookups without permission. A documented command is not permission to run it.
- Never invent versions, benchmarks, costs or compatibility claims.
- Never record secrets in memory.
