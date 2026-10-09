# Trigger evals: change-review

Synthetic prompts. Run them as described in README.md.

## Should trigger

1. Review this diff and tell me whether it is safe to merge.
2. Here is a patch that adds caching to the user lookup. Any bugs or race conditions?
3. Can you look over my last three commits for correctness and missing tests?
4. Check this pull request for security and data-integrity issues.
5. Do the tests in this change really cover the new retry behavior? Review the change.

## Should not trigger

1. The unit test for retries is failing with a timeout. Find the cause.
2. Write an implementation plan for migrating the orders table to a new schema.
3. Compare three stacks for a new mobile backend.
4. Describe the components of this repository and its build commands.
5. Rewrite this function to be shorter and use list comprehensions.
