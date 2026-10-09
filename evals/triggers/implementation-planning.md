# Trigger evals: implementation-planning

Synthetic prompts. Run them as described in README.md.

## Should trigger

1. Plan how to add CSV export to the reports page before we write any code.
2. We need to integrate a payment provider. Break the work into slices with a test matrix.
3. How should we approach splitting the monolith's billing module into a library? Plan only.
4. Draft a rollout plan with rollback steps for changing the user table's primary key.
5. What would it take to add rate limiting to the public API? List affected files and risks.

## Should not trigger

1. The export endpoint returns a 500 for empty reports. Why?
2. Review the attached diff that adds CSV export.
3. Choose a language and framework for a brand-new analytics service.
4. What does this repository contain and how do I build it?
5. Fix the typo in the README heading.
