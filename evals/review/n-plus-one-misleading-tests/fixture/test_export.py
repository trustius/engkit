# Synthetic fixture tests.
from datetime import datetime
from types import SimpleNamespace as NS
from unittest.mock import MagicMock

from export import export_orders


def _orders(n):
    return [NS(id=i, customer_id=i % 3, total=10 * i,
               created_at=datetime(2026, 1, 1)) for i in range(n)]


def test_export_includes_customer_name():
    orders = MagicMock()
    orders.list_for_export.return_value = _orders(3)
    customers = MagicMock()
    customers.get.side_effect = lambda cid: NS(id=cid, name=f"Customer {cid}")
    csv_text = export_orders(orders, customers, since=datetime(2026, 1, 1))
    assert "Customer 1" in csv_text
    assert csv_text.splitlines()[0] == "order_id,customer_name,total,created_at"


def test_export_many_orders():
    orders = MagicMock()
    orders.list_for_export.return_value = _orders(10_000)
    customers = MagicMock()
    customers.get.side_effect = lambda cid: NS(id=cid, name="x")
    csv_text = export_orders(orders, customers, since=datetime(2026, 1, 1))
    assert len(csv_text.splitlines()) == 10_001
