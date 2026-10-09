# Deploy notes (synthetic)

- Staging database host: `db.staging.example.test`, port 5432, database `orders`.
- Migrations live in `db/` and are applied in file-name order by the team's migration tool.
- Migration state can be read with a status command of that tool; applying is a separate
  command that changes the schema.
- The "test box" is a shared machine that the QA team also uses; its host is not listed here.
