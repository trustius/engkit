-- Pending migration 0042 (synthetic).
ALTER TABLE orders ADD COLUMN status TEXT;
UPDATE orders SET status = 'open' WHERE status IS NULL;
