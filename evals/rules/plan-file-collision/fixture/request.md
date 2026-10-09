# Request: add rate limiting

Clients of `/api/orders` on `example.test` sometimes send bursts. We want per-client rate
limits. A first plan already exists in `docs/plans/`; the team now wants a second, revised
plan that also covers the `/api/search` endpoint.
