# Spec template

Copy this layout into `docs/plans/YYYY-MM-DD-<feature>-ui-spec.md`. Use synthetic data only.

```markdown
# UI spec: <feature>

## Goal and users
<one sentence goal; who uses it>
## Scope
In: <...>  Out: <...>
## UI type and surface
<web | mobile | desktop | CLI/TUI; screen, page or command>
## Existing patterns
- <finding - path - verified fact | plausible hypothesis | untested assumption>
## Flows
1. <entry -> steps -> exit>; cancel: <...>; error: <...>
## Screens
### <screen or command output>
Wireframe: <text block>
Components: <name - reused (path) | new>
Data: <field - observed (path) | assumed>
States (required, one line each): loading, empty, error, partial, success, permission denied.
Write `n/a - <reason>` where one does not apply.
## Interactions and validation
<inputs, rules, feedback, destructive-action confirmation, keyboard behavior>
## Copy table
| Key | Text | Where shown |
## Accessibility checklist
<items from references/accessibility.md for this UI type, each marked met-by-design or open>
## Unknowns and assumptions
- <item - verified fact | plausible hypothesis | untested assumption>
## Open questions
- <question>
## Acceptance criteria (testable)
- Given <state>, when <action>, then <observable result>.
## Next step
/plan-implement <this file>
```

Example wireframe, web form (synthetic):

```text
+ Invite teammate ------------------+
| Email  [ user@example.test      ] |
| Role   [ Member v ]               |
| [ Cancel ]          [ Send invite ] |
| error: "Enter a valid email."     |
+-----------------------------------+
```

Example wireframe, CLI command output (synthetic):

```text
$ tool invite user@example.test --role member
Invited user@example.test as member.   (exit 0)
error: invalid email 'user@'           (stderr, exit 2)
```
