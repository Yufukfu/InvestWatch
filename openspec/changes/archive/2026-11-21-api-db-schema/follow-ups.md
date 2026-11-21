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
| 7 | review group 2 | untargeted `ON CONFLICT DO NOTHING` also swallowed a reused `documents.id` | fix-here (`document_insert_ignore_duplicate` targets the dedup index; spec scenario "Reused document id"; README gives the targeted SQL) |
| 8 | review group 2 | republish sweep could re-announce a row an ingest had just committed | fix-here (`older_than` grace on `unpublished_documents`, README uses 1 minute) |
| 9 | review group 2 | `latest_calibration_run` had no tie-break on equal `computed_at` | fix-here (`run_id DESC` as second key, test) |
| 10 | review group 2 | `sources.target_modules` allows duplicates while the contract says `uniqueItems` | new-item (validated in the API's `SourceCreate`/`SourcePatch`, change `api-v1`) |
| 11 | review group 2 | `documents.source_id` has no ON DELETE action, so deleting a source with documents fails | wont-fix (no delete route in `contracts/openapi.yaml`; deactivate with `active=false`) |
| 12 | review group 2 | the `alembic_version` revoke loop would break on a `PUBLIC` grantee | fix-here (`PUBLIC` skipped; revision not yet applied outside test databases) |
| 13 | task 3.2 | manual compose check, 2026-11-21, Docker 28.5.1, project `iw-api-test` on isolated networks: on an empty volume `api-migrate` logged `Running upgrade -> 0001` and `0001 -> 0002` as JSON and exited 0; `iw_app` could read `findings` and had no UPDATE on `alembic_version`; with a wrong admin password it exited 1 with `migration failed: OperationalError`, and the output contained neither password nor URL | docs (copy into the PR body) |
| 14 | task 3.2 | the root `compose.yaml` does not include `api/compose.yaml` yet; network names `iw-data` follow `infra/compose.yaml` on `main`, while `infra-compose` plans project-scoped names | new-item (add the include line and align network names together with `infra-compose`) |
| 15 | Adam's scraper-ingest request (approved by Damian) | `fk_job_errors_source_id` rejected the `invalid_request` error for a scan request naming an unknown source | fix-here (foreign key removed from 0001 and `tables.py`, scenario "Error for an unknown source is recorded"; mutation: re-adding the key turns that test red) |
| 16 | Damian, via the scraper-ingest session | `sources.documents_count`: running count per source or new documents of the last job? | docs (decided: derived on read as a running COUNT, never stored; the scraper writes only `last_run_at` and `last_run_status`) |
| 17 | review groups 3-4 | 0001 was edited in place (job_errors FK) | wont-fix (0001 has only been applied to throwaway test databases; anyone with a local volume from this branch runs `docker compose down -v`; from merge on, changes are new revisions) |
| 18 | review groups 3-4 | README said the root `compose.yaml` already includes `api/compose.yaml` | fix-here (README says it is pending with `infra-compose`; see row 14) |
| 19 | review groups 3-4 | `format_time` cut microseconds to milliseconds | fix-here (microseconds kept, test) |
| 20 | review groups 3-4 | `*_to_contract` needs dict-like rows | docs (docstring: pass `result.mappings()` rows) |
| 21 | review groups 3-4 | admin URL not percent-encoded; a hand-set password with `@:/#%` breaks it | docs (README; generated passwords are hex) |
| 22 | review groups 3-4 | job_errors rows of a deleted source are orphaned (no FK) | wont-fix (no delete route for sources; retention is out of scope for the hackathon) |
| 23 | review groups 3-4 | legacy builder (`DOCKER_BUILDKIT=0`) ignores `api/Dockerfile.dockerignore` and sends the whole root as context | wont-fix (compose v2 builds with BuildKit; nothing outside the explicit COPYs reaches the image) |
| 24 | whole-branch review | URL redaction missed an unencoded `/` or `@` in a password | fix-here (greedy userinfo match, tests with `/`, `@`, `:`) |
| 25 | whole-branch review | comment in 0001 still showed the untargeted `ON CONFLICT DO NOTHING` | fix-here (comment shows the targeted form) |
| 26 | whole-branch review | AI log said 36 mutants; `tasks.md` lines add up to 46 | fix-here |
| 27 | whole-branch review | tasks 3.2, 3.3 and 5.1 read as if the PR-body paste, Adam's hand-over and STATUS were done here | docs (task texts say who does them; STATUS row and blockers go to the coordinating session) |
| 28 | whole-branch review | `documents.text` may be empty (the contract has no `minLength`) | wont-fix (the scraper never stores empty text on a parse failure, `scraper-v1` spec) |
| 29 | whole-branch review | `findings.document_id ON DELETE CASCADE` would erase analyst status and notes if a document were deleted | wont-fix (no route deletes documents) |
| 30 | whole-branch review | base image pinned by tag, pip without `--require-hashes`; uncaught `env.py` tracebacks bypass the JSON redactor (psycopg connect errors carry no password, row 13) | wont-fix (same as the repo's other images; hackathon scope) |
