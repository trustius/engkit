# Deploy process (synthetic)

- Rolling deploy across 12 app instances; old and new versions serve traffic together for
  about 20 minutes.
- Schema migrations run as a pre-deploy step, before any new instance starts.
- Rollback = redeploy the previous app version. Migrations are not rolled back automatically.
- A nightly reporting job (separate repo, separate release cycle) runs
  `SELECT id, fullname, created_at FROM users`.
- Nightly backups are retained for 7 days.
