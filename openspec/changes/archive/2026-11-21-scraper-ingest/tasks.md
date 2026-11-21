# Tasks

Each group from 2 on is one commit. Its first task is the failing test and its last is the mutation check (`iw-commit-cycle` step 3), completed as `mutations: N tried, N caught` (or `mutations: n/a, <reason>`). Groups 1 and 4 are agreements and docs only. Tests that need PostgreSQL, Redis or MinIO run against containers (compose file: task 1.1, or plain `docker run` until it lands).

## 1. Agreements

- [x] 1.1 Agreed with Damian (Damian's reply, 2026-11-21): he writes the Alembic revision `0001_initial` (branch `api/api-v1`; the README of `api/` on that branch has the scraper SQL); `documents.source_id` and `content_hash` are real columns; `documents_count` is not stored (the API counts it on read); redis, minio and `minio-init` (creates `iw-raw`) come with his `infra-compose` change; the plan fix is ours (4.1). The throwaway test schema `scraper/tests/schema.sql` mirrors his DDL

## 2. Document build and insert

- [x] 2.1 Failing tests, then building the full document (`id` UUID v4, `fetched_at`, `scrape_meta` with `duration_ms` and proxy id, `source_id`) from a parsed page; contract-minimum fields present
- [x] 2.2 Failing tests, then schema validation against `CONTRACTS_DIR`; the valid, `schema_invalid` and blank-text (`empty_text`) scenarios pass (needs `contracts/requirements.txt`)
- [x] 2.3 Failing tests, then `content_hash` over the normalised text, a dedup check, and insert with `ON CONFLICT DO NOTHING` returning an `IngestResult`; rerun, whitespace-only, case and changed-page scenarios pass against a real PostgreSQL (throwaway test schema)
- [x] 2.4 Mutation check; `mutations: 11 tried, 11 caught` (one survivor, `is_duplicate` ignoring `source_id`, found a missing test and was caught after adding it)

## 3. Storage, publish, sweep, error sink

- [x] 3.1 Failing tests, then the startup bucket check (`BucketMissing`; the bucket is never created), HTML upload to `iw-raw`, `html_object_key`, and object removal on a conflict or any later insert error; stored, bucket-missing, `storage_error`, no-stray-object and insert-fails scenarios pass against a real MinIO
- [x] 3.2 Failing tests, then `XADD iw:documents` after commit and `publish_failed` recording; the event-after-commit, insert-fails and Redis-down scenarios pass
- [x] 3.3 Failing tests, then the republish sweep (unpublished and older than the grace period, `FOR UPDATE SKIP LOCKED`); the sweep, fresh-row, concurrent-sweeps and marker-failure scenarios pass
- [x] 3.4 Failing test, then the database `job_errors` sink (nullable `source_id`); each reason is stored and no credential is recorded
- [x] 3.5 Mutation check; `mutations: 76 tried, 74 caught, 2 equivalent` (one survivor, the sweep's `ORDER BY created_at, id`, found a missing oldest-first test; a `FOR UPDATE` without `SKIP LOCKED` mutant hung the first run's teardown, so the sweep test now always releases its gate and fails fast; the review-fix round added 11 mutants on redaction, the detail cap, cancel cleanup, the broadened catches and the publish timeout, and one survivor, the dedup pre-check catch, got its test; the whole-branch round added 22 more: redaction (pre-cap, bearer, userinfo, nested pairs, source_id order and log), `html_object_key`, returned-error redaction and the publish catch, with one survivor that got a test and one equivalent mutant, a redundant URL regex, that was removed)

## 4. Closing

- [x] 4.1 Apply the `iw-docs-update` skill (`scraper/CLAUDE.md`, your row in `.docs/STATUS.md`), run docs-check, add the `iw-ai-log` row, and fix `.docs/integration-plan.md` §3 and §6 to match `source.schema.json` and `events.schema.json` (record the bucket-check, named-conflict-target and `created_at`-sweep decisions in an ADR if `iw-docs-update` requires one)
- [x] 4.2 Run the `iw-pr-review` skill and fix real findings; `iw-reviewer` reports no open blocking findings

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
