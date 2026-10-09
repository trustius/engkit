# Trigger evals: engineering-onboard

Synthetic prompts. Run them as described in README.md.

## Should trigger

1. /engineering-onboard I just joined this team. Map out this repository's components and how to build and test them.
2. What is this project built with? Look at the manifests and tell me.
3. Document the conventions and documented test commands of this monorepo, without running anything.
4. Which package manager does apps/web use? There seem to be two lockfiles.
5. Explore this unfamiliar codebase and record what you learn about each component in project memory.

## Should not trigger

1. Our integration test fails intermittently. Find the root cause.
2. Plan a migration of this project from one build tool to another.
3. Recommend a stack for a new project that has no code yet.
4. Review the diff in pull request 42.
5. Run the test suite and tell me what fails.

### Argument cases

- 1. With argument: `/engineering-onboard apps/web` -> Maps only apps/web read-only and writes context entries to .engkit/memory/ (or says to run engkit init if missing).
- 2. Without argument: `/engineering-onboard` -> Maps the whole project read-only, presents labelled findings, then writes context entries to .engkit/memory/; runs no project commands.
