# Follow-ups: api-db-schema

Out-of-scope or "declined to judge" items from reviews, each with one disposition (`fix-here`, `new-item`, `wont-fix`, `docs`).

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | review group 1 | `JsonFormatter` wrote full exception text: URL credentials and SQLAlchemy `[parameters: ...]` could reach stdout | fix-here (`redact()` on message and exception, tests with a DSN password and SQL parameters) |
| 2 | review group 1 | test fixture ran `CREATE/ALTER ROLE` on any server and never dropped the role; concurrent sessions overwrote each other's password | fix-here (localhost only unless `TEST_DATABASE_ALLOW_REMOTE=1`, random role per session, dropped with the databases) |
| 3 | review group 1 | `TestDatabase` repr printed URLs with passwords in pytest failure output; the name triggered pytest collection warnings | fix-here (`field(repr=False)`, renamed `TempDatabase`) |
| 4 | review group 1 | `json.dumps` without `default=str` lost a log line on a non-serialisable extra | fix-here |
| 5 | review group 1 | task 1.3 named `TEST_DATABASE_APP_URL`, which the fixture does not use (it generates the app role) | docs (task text updated) |
| 6 | mutation check group 1 | `GRANT USAGE ON SCHEMA public` is redundant on Postgres 17 (PUBLIC already has USAGE), also in `infra/postgres/init/01-app-role.sh` | wont-fix (harmless and explicit; it matters if `public` is ever locked down) |
