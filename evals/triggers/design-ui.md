# Trigger evals: design-ui

Synthetic prompts. Run them as described in README.md.

## Should trigger

1. /design-ui let admins invite teammates by email
2. Design the settings screen for notification preferences before we build it.
3. Sketch the flow and states for a bulk-import dialog in the admin console, with wireframes and copy.
4. We need a new `status` command for the CLI. Design its output and flags first; no code yet.
5. Write a UI spec for the checkout confirmation page, reusing our existing components.

## Should not trigger

1. Code the signup form from the design we agreed on.
2. Fix the misaligned button on the pricing page.
3. Review this diff that changes the navbar.
4. Which front-end framework should we use for the new admin console?
5. Plan the implementation slices for docs/plans/2026-10-09-invite-ui-spec.md.

### Argument cases

- 1. With argument: `/design-ui let admins invite teammates by email` -> Surveys the project read-only, writes only the spec file `docs/plans/YYYY-MM-DD-<slug>-ui-spec.md` (no code, style or config edited) and ends with Next step `/plan-implement <spec file>`.
- 2. Without argument: `/design-ui` -> Asks what to design, for whom and on which surface (screen, page or command); writes nothing yet.
