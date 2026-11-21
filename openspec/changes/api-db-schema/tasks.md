# Tasks

Lands before change `api-v1`: groups 1-3 unblock `scraper-v1` group 5 (Adam) and the analytics storage step for Integration #1 (Sat 17:00). Group 4 can follow after Integration #1 if time is short.

## 1. Package skeleton and test database

- [x] 1.1 `api/CLAUDE.md` and `api/README.md` exist (written with this proposal); `node .claude/skills/iw-docs-update/scripts/docs-check.mjs` passes
- [x] 1.2 Failing test first (`api/tests/test_settings.py`: missing `DATABASE_ADMIN_URL` raises an error naming the variable), then `api/pyproject.toml`, pinned `requirements.txt` / `requirements-dev.txt` (sqlalchemy, alembic, psycopg[binary], pytest), `src/investwatch_api/settings.py` and a JSON log formatter; `pytest api` is green
- [x] 1.3 Test fixture that connects with `TEST_DATABASE_ADMIN_URL` (localhost only unless `TEST_DATABASE_ALLOW_REMOTE=1`), creates throwaway databases and a per-session app role with the same grants as `infra/postgres/init/01-app-role.sh`, drops both afterwards, and skips (not fails) when the variable is unset; documented in `api/README.md`
- [x] 1.4 Mutation check (iw-commit-cycle step 3); mutations: 9 tried, 8 caught, 1 equivalent (removing `GRANT USAGE ON SCHEMA public` from the fixture survives because Postgres 17 grants USAGE on `public` to PUBLIC; same redundancy in `infra/postgres/init/01-app-role.sh`); review fixes: mutations: 6 tried, 6 caught

## 2. Initial revision: tables, constraints, dedup and upsert keys

- [ ] 2.1 Failing tests for the scenarios "Empty database is migrated", "Migration is idempotent", "Downgrade removes the tables" and "Application role has CRUD but no DDL"
- [ ] 2.2 Core `Table` definitions in `src/investwatch_api/db/tables.py` and Alembic `env.py` reading `DATABASE_ADMIN_URL`; revision `0001_initial` for `sources`, `documents`, `findings`, `job_errors`, `calibration_points` with the CHECK constraints from `contracts/schemas/` and the `alembic_version` revoke; the 2.1 tests pass
- [ ] 2.3 Failing tests, then the dedup index and `stream_published_at` with its partial index: all "Documents are deduplicated per source" and "Published-to-stream marker" scenarios pass
- [ ] 2.4 Failing tests, then the `(document_id, module)` unique key and the documented upsert statement as a helper `findings_upsert()` in `src/investwatch_api/db/sql.py` (the API's tests and analytics can copy the SQL): "One finding per document and module" scenarios pass
- [ ] 2.5 Failing tests, then the enum, range and not-null constraints: "Unknown enum value is rejected", "Score out of range is rejected", "Required contract field missing", "Empty reason is rejected", the job-error and calibration scenarios pass
- [ ] 2.6 Mutation check; line reads `mutations: N tried, N caught`

## 3. Contract round-trip and the migrate service

- [ ] 3.1 Failing test, then `src/investwatch_api/db/mapping.py` (contract dict ↔ row): "Contract mock round-trips" passes for every item of `contracts/mocks/documents.json`, `findings.json` and `sources.json`, and each read-back passes `contracts/validate.py`
- [ ] 3.2 `api/Dockerfile` (python:3.13-slim, non-root, `CONTRACTS_DIR` set) and `api/compose.yaml` with the one-shot `api-migrate` service on `iw-data`, admin URL built from `POSTGRES_ADMIN_*`; with the root `include:` line coordinated with `infra-compose`, "Stack starts on an empty volume" and "Migration fails" are checked by hand (`docker compose up`, then a wrong admin password) and the output pasted in the PR body
- [ ] 3.3 Write the exact insert SQL for the scraper (`ON CONFLICT DO NOTHING`, marker update, sweep query) and for analytics (upsert) into `api/README.md`; tell Adam that `scraper-v1` task 1.4 is answered
- [ ] 3.4 Mutation check; line reads `mutations: N tried, N caught`

## 4. Query indexes

- [ ] 4.1 Failing tests, then the indexes on `findings` (`detected_at DESC`, `module`, `status`, `platform`, `score`) and `job_errors (source_id, occurred_at)` in revision `0002_query_indexes`: "Default list query uses an index" and "Sweep query uses the index" pass on seeded data
- [ ] 4.2 Mutation check; line reads `mutations: N tried, N caught`

## 5. Closing

- [ ] 5.1 Apply the `iw-docs-update` skill (`api/CLAUDE.md`, `api/README.md`, ADR 0307 and its row in `.docs/decisions/README.md`, the `api` row in the root `CLAUDE.md` services table and in `.docs/INDEX.md`, Damian's row in `.docs/STATUS.md`, the STATUS blocker about `api/` and the migration owner), run docs-check, run `pip-audit -r api/requirements.txt -r api/requirements-dev.txt` and record it in `.docs/security-audit.md`, and add the `iw-ai-log` row
- [ ] 5.2 Run the `iw-pr-review` skill and fix real findings; `iw-reviewer` reports no open blocking findings

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
