# Trigger evals: bug-investigate

Synthetic prompts. Run them as described in README.md.

## Should trigger

1. The checkout test test_apply_discount started failing after yesterday's merge with a KeyError. Find out why.
2. Our nightly export job sometimes writes duplicate rows. I can't reproduce it locally. What is going on?
3. Users report a 500 on /login only on the staging server. Here is the log excerpt. Why?
4. This function returns None instead of a list when the input is empty and I don't see why. Debug it.
5. Our worker randomly hangs after about two hours. Help me find the root cause.

## Should not trigger

1. Review this pull request diff for problems before I merge it.
2. Plan how we should add two-factor login to the app, step by step.
3. Which web framework and database should we use for a new invoicing tool?
4. Summarize how this repository is organized and how to run its tests.
5. Rename the variable total to subtotal across the file.
