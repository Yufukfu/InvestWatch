# Tasks

Each group from 2 on is one commit. Its first task is the failing test and its last is the mutation check (`iw-commit-cycle` step 3), completed as `mutations: N tried, N caught` (or `mutations: n/a, <reason>`). Groups 1 and 4 are agreements and docs only. Tests that need PostgreSQL, Redis or MinIO run against containers (compose file: task 1.1, or plain `docker run` until it lands).

## 1. Agreements

- [ ] 1.1 Send `migration-request.md` to C and agree: who writes the Alembic migration (unique index `(source_id, content_hash)`, `committed_at` and `stream_published_at`, `job_errors` with nullable `source_id` and no foreign key, `sources.last_run_status` and `documents_count`), who provides `docker-compose.yml` (postgres, redis, minio), that `documents.source_id` and `content_hash` are real columns, that the dashboard reads `sources.documents_count` as the last job's new documents, and that `.docs/integration-plan.md` §3 and §6 are stale against the schemas; record in `.docs/STATUS.md`. Groups 2-3 do not wait for it (throwaway test schema); the real migration is exercised in `scraper-orchestration`

## 2. Document build and insert

- [ ] 2.1 Failing tests, then building the full document (`id` UUID v4, `fetched_at`, `scrape_meta` with `duration_ms` and proxy id, `source_id`) from a parsed page; contract-minimum fields present
- [ ] 2.2 Failing tests, then schema validation against `CONTRACTS_DIR`; the valid and `schema_invalid` scenarios pass (needs `contracts/requirements.txt`)
- [ ] 2.3 Failing tests, then `content_hash` over the normalised text, a dedup check, and insert with `ON CONFLICT DO NOTHING` returning an `IngestResult`; rerun, whitespace-only, case and changed-page scenarios pass against a real PostgreSQL (throwaway test schema)
- [ ] 2.4 Mutation check; `mutations:`

## 3. Storage, publish, sweep, error sink

- [ ] 3.1 Failing tests, then bucket creation at startup, HTML upload to `iw-raw`, `html_object_key`, and object removal on a conflict or any later insert error; stored, `storage_error`, no-stray-object and insert-fails scenarios pass against a real MinIO
- [ ] 3.2 Failing tests, then `XADD iw:documents` after commit and `publish_failed` recording; the event-after-commit, insert-fails and Redis-down scenarios pass
- [ ] 3.3 Failing tests, then the republish sweep (unpublished and older than the grace period, `FOR UPDATE SKIP LOCKED`); the sweep, fresh-row, concurrent-sweeps and marker-failure scenarios pass
- [ ] 3.4 Failing test, then the database `job_errors` sink (nullable `source_id`); each reason is stored and no credential is recorded
- [ ] 3.5 Mutation check; `mutations:`

## 4. Closing

- [ ] 4.1 Apply the `iw-docs-update` skill (`scraper/CLAUDE.md`, your row in `.docs/STATUS.md`), run docs-check, and add the `iw-ai-log` row
- [ ] 4.2 Run the `iw-pr-review` skill and fix real findings; `iw-reviewer` reports no open blocking findings

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
