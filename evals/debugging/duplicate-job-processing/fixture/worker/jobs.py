# Synthetic fixture. Not a real service.
from .mail import send  # not included in fixture


def send_invoice_email(db, payload):
    invoice = db.query_one("SELECT id, customer_email, total FROM invoices WHERE id = ?",
                           (payload["invoice_id"],))
    send(to=invoice.customer_email, subject=f"Invoice {invoice.id}",
         body=f"Amount due: {invoice.total}")
    db.execute("INSERT INTO email_log (invoice_id, sent_at) VALUES (?, now())", (invoice.id,))


HANDLERS = {"send_invoice_email": send_invoice_email}
