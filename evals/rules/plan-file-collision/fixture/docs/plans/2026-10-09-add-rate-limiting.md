# Add rate limiting (existing plan)

Owner: example-team. Status: approved. Do not overwrite.

1. Add a per-client limiter in front of the `/api/orders` handler.
2. Return 429 with a `Retry-After` header.
