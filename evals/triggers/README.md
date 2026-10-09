# Trigger evals

These check whether a skill is invoked on the right prompts and left alone on near-misses.
Each skill has a file `<skill-name>.md` with 5 prompts under `## Should trigger` and 5 under
`## Should not trigger`. Prompts are synthetic.

## How to run

1. Create a fresh temporary project and install only the skill under test with
   `engkit install <skill-name> --target claude --project-dir <temp-project>` (or `--target codex`).
2. For each prompt, start a fresh session with no prior conversation, in Claude Code or Codex.
3. Paste the prompt verbatim and record whether the skill was invoked.
4. Run every prompt 3 times per model. A skill passes for a model when, in all 3 runs, all 5
   should-trigger prompts invoke it and none of the 5 should-not prompts do. Otherwise it
   fails. Record the platform version and exact model next to the result.
5. Never invent results. A cell stays `not-run` until a real session was executed.

## Argument cases

Each skill file also lists two argument cases under `### Argument cases`: the command typed
with an argument, and the bare command. Run them the same way (fresh session, 3 runs) and
check the expected behavior described; they are not counted in the 5+5 trigger prompts.
Results stay `not-run` until a real session was executed.

## Results

Allowed values: `pass`, `fail`, `not-run`. No agent runs have been performed yet.

| Skill | Claude Code + Haiku | Claude Code + Sonnet | Codex (model recorded) |
|---|---|---|---|
| bug-investigate | not-run | not-run | not-run |
| change-review | not-run | not-run | not-run |
| plan-implement | not-run | not-run | not-run |
| engineering-onboard | not-run | not-run | not-run |
| stack-select | not-run | not-run | not-run |
| memory-save | not-run | not-run | not-run |
| implement-plan | not-run | not-run | not-run |
| design-ui | not-run | not-run | not-run |
