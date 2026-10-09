# ExamplePay API — excerpt (fictional, synthetic)

Base URL: `https://api.examplepay.test/v1`
Auth: `Authorization: Bearer <API_KEY>` (use `PLACEHOLDER_API_KEY` in examples)

## Create payment
`POST /payments`

Body: `{"amount": <int minor units>, "currency": "EUR", "reference": "<your order ref>"}`

Response `201`: `{"id": "pay_...", "status": "succeeded" | "pending" | "failed"}`
Response `402`: card declined. Response `5xx`: try again later.

Requests may include an `Idempotency-Key` header. Idempotency keys are supported.

## Get payment
`GET /payments/{id}` returns the payment object.
`GET /payments?reference=<ref>` returns payments created with that reference.

## Webhooks
`payment.succeeded` and `payment.failed` events are sent to your configured endpoint.
Events may be delivered more than once.

## Timeouts
Clients should use a timeout of at least 30 seconds.
