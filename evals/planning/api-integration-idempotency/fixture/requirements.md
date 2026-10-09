# Checkout payments — requirements (synthetic)

- R1. Replace the stub charge with ExamplePay.
- R2. Customers must never be charged twice for one order.
- R3. Checkout must survive provider timeouts and transient errors.
- R4. An order is marked paid only after the provider confirms success.
- R5. Support staff need to see the payment state of any order.
- Open: product has not decided whether "pending" payments block shipping.
