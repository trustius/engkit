# debugging/cookie-domain-mismatch

Skill: bug-investigate

## Prompt

```
Users report a login loop after last week's deploy: they enter valid credentials, get
redirected to the dashboard, and immediately land back on the login page. It happens in
staging and production, not on developer machines. The code and a captured request log are
in this directory. Find the root cause and propose a fix. Do not change any files.
```

## Fixture

`fixture/` — a tiny synthetic web app (Python-like, not runnable as a service) split between
`auth.example.test` (login) and `app.example.test` (dashboard):

- `app/config.py` — cookie settings; `SESSION_COOKIE_DOMAIN` defaults to the auth host.
- `app/session.py` — sets and reads the session cookie.
- `app/routes.py` — login handler and the dashboard guard that redirects to login.
- `logs/staging-requests.log` — synthetic request/response trace showing the loop.
- `CHANGELOG.md` — last deploy notes, including a red herring (session TTL change).

## Rubric

Dimensions: factual correctness, evidence quality, false positives, regression coverage,
unnecessary work. Case-specific:

- Distinguishes the verified fact (log shows `Domain=auth.example.test` on `Set-Cookie`
  and no `Cookie` header on the `app.example.test` request) from hypotheses.
- Explains why local dev differs (both served from `localhost`, so host-only cookie works).
- Considers and rejects the TTL change with evidence (TTL is 3600 s; the loop happens within
  a second).

## Critical expected findings

1. The session cookie is scoped to `auth.example.test`, so the browser does not send it to
   `app.example.test`; the dashboard guard sees no session and redirects to login.
2. Cause is the `SESSION_COOKIE_DOMAIN` default introduced in the last deploy
   (`config.py`, changelog entry), not credentials or the TTL change.
3. Fix: set the cookie domain to the shared parent (`example.test` / `.example.test`) via
   configuration, or serve both on one host; note security trade-off of a parent-domain
   cookie (sent to all subdomains) and keep `Secure`/`HttpOnly`/`SameSite`.
4. Regression test: a test asserting the `Set-Cookie` domain matches the dashboard host
   (or that a login followed by a dashboard request on the other host is authenticated).

## Disallowed hallucinations

- Claiming the password check, hashing or user store is at fault.
- Claiming the TTL change causes the loop.
- Citing files, lines, headers or log entries that do not exist in the fixture.
- Claiming the fix was applied or tests were run.
- Blaming a specific browser version or vendor without evidence.

## Pass threshold

Findings 1, 2 and 3 hit; no disallowed hallucination; no dimension scores 0; evidence
quality = 2.
