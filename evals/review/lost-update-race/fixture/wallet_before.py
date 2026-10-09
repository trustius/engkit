# Synthetic fixture. Not a real service.
class InsufficientFunds(Exception):
    pass


def debit(db, account_id, amt, reason):
    with db.transaction():
        changed = db.execute(
            "UPDATE accounts SET balance = balance - ? WHERE id = ? AND balance >= ?",
            (amt, account_id, amt),
        )
        if changed == 0:
            raise InsufficientFunds(account_id)

