# Synthetic fixture. Not a real service.
from .payments import charge  # stub today; returns {"status": "succeeded"}


def checkout(db, cart, customer):
    order = db.insert_order(customer_id=customer.id, total=cart.total, status="new")
    attempts = 0
    while True:
        try:
            result = charge(amount=cart.total, currency="EUR", reference=str(order.id))
            break
        except Exception:  # noqa: BLE001
            attempts += 1
            if attempts >= 3:
                db.update_order(order.id, status="payment_error")
                raise
    if result["status"] == "succeeded":
        db.update_order(order.id, status="paid")
    else:
        db.update_order(order.id, status="payment_failed")
    return order
