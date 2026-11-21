# 0104. Ingest order, at-least-once delivery and the republish sweep

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by: pending approval of the `scraper-ingest` PR

## Context

The scraper turns a parsed page into a `documents` row, the raw HTML in MinIO and an `iw:documents` event that analytics consumes ([integration-plan.md](../integration-plan.md) §2-§3, spec `document-ingest` in [`openspec/changes/scraper-ingest/`](../../openspec/changes/archive/2026-11-21-scraper-ingest/)). PostgreSQL, MinIO and Redis cannot commit together, so some order of the three writes has to be chosen and a failure between them has to leave something recoverable. [`events.schema.json`](../../contracts/schemas/events.schema.json) already says the message is "published only after the document row is committed".

## Options considered

1. **`XADD` before the commit.** A consumer can read a `document_id` whose row does not exist yet or never will. The test `test_event_follows_the_commit` fails for this order (a mutant that publishes before the insert is caught).
2. **`XADD` after the commit, nothing else.** A crash or a Redis outage between the two loses the announcement for good: the row exists and is never analysed. `test_redis_down_keeps_the_row_unpublished_and_records_publish_failed` shows the state this leaves.
3. **Commit, then `XADD`, with a published marker and a republish sweep.** The row carries `stream_published_at` (`NULL` = not announced). A sweep announces rows that are unpublished and older than a grace period. Damian's migration already has the marker and a partial index for exactly this query (`ix_documents_unpublished` in `api/migrations/versions/0001_initial.py`), and the README of `api/` gives the sweep SQL (oldest first, one-minute grace).
4. **One transaction across PostgreSQL and Redis.** Not possible: there is no shared commit between them.

## Decision

Option 3.

- **Order:** validate, cheap dedup lookup, upload HTML to `iw-raw`, insert (commit), then `XADD iw:documents * document_id <uuid> schema v1`, then set `stream_published_at`. Any failure before the commit removes the uploaded object and publishes nothing; a failure after it records `publish_failed` and leaves the row for the sweep.
- **Delivery is at-least-once.** A crash between `XADD` and the marker update publishes twice. Consumers deduplicate by `document_id`.
- **Sweep:** `created_at < now() - grace` (default 60 s, the same as Damian's SQL), `ORDER BY created_at, id`, `FOR UPDATE SKIP LOCKED`. The row lock separates concurrent sweeps (`test_concurrent_sweep_skips_rows_claimed_by_a_running_one`); only the grace period protects a run that is still publishing its own fresh row. `XADD` is bounded by a timeout so a hung Redis cannot hold the locks.
- **Dedup insert** names its conflict target, `ON CONFLICT (source_id, content_hash) WHERE content_hash IS NOT NULL DO NOTHING`, as Damian's `api/` README requires: a bare `ON CONFLICT DO NOTHING` would also hide a reused `id`.
- **Bucket:** the scraper checks that `iw-raw` exists and fails clearly; it never creates it. Damian's `minio-init` creates it and the app user is limited to that bucket, so it may lack the permission.

## Consequences

- Analytics must treat `iw:documents` as at-least-once. That is already how the plan describes the stream (consumer group, `XPENDING` / `XCLAIM`).
- Nothing calls `Ingestor`, `sweep` or `Storage.check_bucket` yet. Scheduling the sweep, calling `check_bucket` at startup, the sink adapter and the `page` dict are wiring that still has to be assigned between `scraper-v1` and `scraper-orchestration` (follow-up 1 in [`follow-ups.md`](../../openspec/changes/archive/2026-11-21-scraper-ingest/follow-ups.md)).
- A hard crash between the upload and the insert can still leave an orphan object. Cancellation and every error path remove it; a periodic list-and-diff of `iw-raw` against `documents.html_object_key` is a possible follow-up.
- The stream is capped on every publish with `MAXLEN ~ 10000`, as `infra/README.md` requires (Redis runs `noeviction` with 128 MB, so a full stream fails every write). A consumer that falls more than about 10 000 entries behind loses the oldest ones, and the sweep does not bring them back, because their rows are already marked published.
- A schema change needs a new Alembic revision from Damian; the test schema `scraper/tests/schema.sql` mirrors `0001_initial` and has to follow it.
