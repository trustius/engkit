# Synthetic fixture tests (sequential only).
import pytest
from wallet import debit, InsufficientFunds


def test_debit_reduces_balance(fake_db):
    fake_db.seed_account(1, balance=100)
    assert debit(fake_db, account_id=1, amount=30, reason="t") == 70
    assert fake_db.balance(1) == 70


def test_debit_rejects_overdraft(fake_db):
    fake_db.seed_account(1, balance=10)
    with pytest.raises(InsufficientFunds):
        debit(fake_db, account_id=1, amount=30, reason="t")


def test_debit_writes_ledger(fake_db):
    fake_db.seed_account(1, balance=50)
    debit(fake_db, account_id=1, amount=5, reason="fee")
    assert fake_db.ledger(1) == [(-5, "fee")]
