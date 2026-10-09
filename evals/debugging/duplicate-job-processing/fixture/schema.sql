-- Synthetic fixture schema. Engine intentionally unspecified.
CREATE TABLE jobs (
  id          BIGINT PRIMARY KEY,
  kind        TEXT NOT NULL,
  payload     TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'pending',  -- pending | running | done | failed
  claimed_by  TEXT,
  claimed_at  TIMESTAMP,
  error       TEXT,
  created_at  TIMESTAMP NOT NULL
);

CREATE TABLE email_log (
  id          BIGINT PRIMARY KEY,
  invoice_id  BIGINT NOT NULL,   -- no unique constraint
  sent_at     TIMESTAMP NOT NULL
);
