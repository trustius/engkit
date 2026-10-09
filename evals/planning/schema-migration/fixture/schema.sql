-- Synthetic fixture. Relational datastore; engine intentionally not specified.
-- users: approx. 40 million rows; peak write rate ~300 rows/s.
CREATE TABLE users (
  id          BIGINT PRIMARY KEY,
  email       TEXT NOT NULL UNIQUE,
  fullname    TEXT NOT NULL,
  created_at  TIMESTAMP NOT NULL,
  updated_at  TIMESTAMP NOT NULL
);

CREATE INDEX users_created_at_idx ON users (created_at);
