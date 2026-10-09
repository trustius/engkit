# Synthetic fixture. Not a real service.
class CustomerRepo:
    def __init__(self, db):
        self.db = db

    def get(self, customer_id):
        # one round trip per call; returns None if not found
        return self.db.query_one(
            "SELECT id, name FROM customers WHERE id = ?", (customer_id,)
        )

    def get_many(self, customer_ids):
        # single round trip; returns {id: row}
        ids = list(set(customer_ids))
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        rows = self.db.query_all(
            f"SELECT id, name FROM customers WHERE id IN ({placeholders})", ids
        )
        return {r.id: r for r in rows}


class OrderRepo:
    def __init__(self, db):
        self.db = db

    def list_for_export(self, since):
        return self.db.query_all(
            "SELECT id, customer_id, total, created_at FROM orders WHERE created_at >= ?",
            (since,),
        )
