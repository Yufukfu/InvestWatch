# Design

## Context

`analytics-skeleton` (not merged yet) provides `analyze(doc, *, registry, catalogue, now) -> list[Finding]`, Pydantic `ScrapedDocument` (lenient) and `Finding` (strict), JSON logging, and `config.py` with `REGISTRY_CSV` and `LOG_LEVEL`. This change wraps it in I/O, following `.docs/analytics-plan.md` §12.2-12.3 steps 7-9, `.docs/integration-plan.md` §2 (points 1, 3-5) and §6, and ADRs 0303 (Alembic migrations in `api/`) and 0305 (thresholds in Redis, analytics emits `finding.high_risk`). The scraper (`scraper-v1` design) publishes to `iw:documents` after its commit and has a republish sweep. Delivery is therefore at least once, and analytics must deduplicate by `document_id`. `infra/` (B) already runs Postgres with roles `iw_admin` (DDL) and `iw_app` (CRUD) on the internal network `iw-data`. Redis and MinIO come from the sibling change `infra-compose`.

## Goals / Non-Goals

**Goals:**
- A message on `iw:documents` becomes committed `findings` rows and `iw:events` messages, with XACK only after the commit.
- Safe under redelivery, crashes, a second worker and outages of Redis and Postgres. Poison messages never block the stream.
- Everything except the Postgres and Redis adapters is testable with the in-memory store, `fakeredis` and the no-op publisher.

**Non-Goals:**
- Creating or migrating tables (ADR 0303), Redis, MinIO or network setup (`infra-compose`).
- The LLM, its Redis cache, M1/M3, MinIO reads (`html_object_key`, screenshots), a dead-letter stream, and metrics beyond logs and `/health`.

## Decisions

1. **Synchronous, one message at a time.** Use `redis-py` and `psycopg` 3 (sync) with a single loop: claim stale, read with `COUNT 1 BLOCK STREAM_BLOCK_MS`, then process. Rules-only analysis takes milliseconds, so throughput comes from running more containers in the same group, not from async. Alternative: asyncio with `redis.asyncio` and `psycopg` async. Rejected because it adds complexity with no measured need, and the LLM change can revisit it.
2. **Processing order: load, analyze, save (one transaction, commit), publish, XACK.** This is the only order in which an acknowledged message implies durable findings. The cost is that events are at most once: a crash between commit and publish loses them. The finding is still in the DB, and the dashboard's REST list shows it. Alternative: an outbox table with a relay. It is the correct fix but needs a migration in `api/` and a second loop, so it is deferred and raised as an open question.
3. **Idempotency by `document_id`.** Before analyzing, the worker asks `findings_for_document(document_id)`. If any finding exists, the message is acknowledged as `already_processed`. A document with zero findings is cheap to re-analyze and has nothing to duplicate. Alternative: a processed-ids set in Redis. Rejected because it can disagree with the DB after a failed commit.
4. **Re-scan identity `(url_key, module)` with `url_key = coalesce(canonical_url, url)`.** This follows the UKNF requirement quoted in plan §4: a document from the same URL updates the finding. The upsert is `INSERT ... ON CONFLICT (url_key, module) DO UPDATE ... WHERE <existing document's fetched_at> <= EXCLUDED fetched_at`. A unique index makes concurrent workers safe, and the guard stops a late redelivery of an older document from overwriting newer results. `RETURNING id, (xmax = 0) AS created` tells insert from update. The stale case returns no row and is reported `skipped_stale`. `status`, `id` and `detected_at` are never overwritten, because analysts own `status` (`PATCH /findings/{id}`). The guard needs the existing document's `fetched_at`. The plan is a stored `source_fetched_at` column on `findings` rather than a join inside the upsert **[reconcile-api]**.
5. **Error taxonomy drives ack/no-ack.** The store and the loader raise `NotFound`, `InvalidDocument` (wrapping Pydantic's error and naming the field) or `StoreUnavailable` (connection loss, `SerializationFailure`, `OperationalError`). `NotFound` and `InvalidDocument` are acked as poison. `StoreUnavailable` and Redis `ConnectionError` cause backoff and no ack. Any other exception is a suspected bug: the message is left pending, and once its delivery count (from `XPENDING` / the XAUTOCLAIM entry) reaches `MAX_DELIVERIES` it is acked as `max_deliveries_exceeded`, with the traceback logged. Backoff is capped exponential (1, 2, 4 … 30 s) with jitter.
6. **XAUTOCLAIM every loop iteration, with `COUNT 10` and `JUSTID` off.** It is cheap and reclaims both this consumer's own pending entries after a restart and those of a dead consumer. The group is created with `XGROUP CREATE iw:documents analytics 0 MKSTREAM`, and `BUSYGROUP` is ignored. Starting at `0` instead of `$` means documents the scraper sent before analytics' first start are not lost, at the cost of one full pass over the stream backlog on the very first start.
7. **Threshold read per finding, no cache.** `GET iw:settings:thresholds` is parsed as a JSON object, matching the REST `Thresholds` schema (`contracts/openapi.yaml`). The API (ADR 0305) writes it, and the exact format is **[reconcile-api]**. Invalid or missing values fall back per module to 0.6 / 0.5 / 0.7. One GET per new finding is negligible.
8. **Events are built from the persisted finding,** so the `id` is the stored one after an upsert. The publisher serializes the `event` envelope with `emitted_at = now()` and no `risk_level`. Tests validate it against `events.schema.json` when `CONTRACTS_DIR` is set, the same skip rule as the skeleton's contract tests.
9. **Document loading:** `SELECT` the simple columns plus `payload`, merge them as `{**payload, **columns}`, then `ScrapedDocument.model_validate`. Columns win, because they are what the scraper indexes and deduplicates on.
10. **`/health` with stdlib `http.server` in a daemon thread.** It is the convention every service follows (§7) without pulling in a web framework. It pings Redis and runs `SELECT 1` with a 1 s timeout. The Docker HEALTHCHECK calls it with `python -c` (the slim image has no curl).
11. **Container.** The Dockerfile is `public.ecr.aws/docker/library/python:3.13-slim` (infra rule: images from the ECR mirror). It installs pinned requirements first for layer caching, copies `src/` and `registry/`, creates user `iw` (uid 10001) and sets `USER 10001`. The entrypoint is `python -m investwatch_analytics.worker`. `analytics/compose.yaml` follows `web/compose.yaml`: `read_only: true`, `tmpfs /tmp`, `cap_drop: [ALL]`, `no-new-privileges`, CPU and memory limits, the networks `iw-data` (Postgres) and Redis's network **[reconcile-infra]**, and `depends_on` on healthy Postgres and Redis plus the completed API migration job **[reconcile-api]**. `iw-data` is internal, so a hosted LLM later needs an egress network. That is not needed in this change. The skeleton targets `>=3.12`, and the image pins 3.13.
12. **Config additions** in `config.py`, all env-only: `DATABASE_URL` and `REDIS_URL` (required for the worker, not for the CLI), `WORKER_CONSUMER` (default hostname), `STREAM_BLOCK_MS` (5000), `CLAIM_MIN_IDLE_MS` (60000), `MAX_DELIVERIES` (5) and `HEALTH_PORT` (8001). Stream, group, channel and key names are contract constants in code, not env.

No ADR: the irreversible choices (schema ownership, threshold storage, event producer) are already ADRs 0303 and 0305. The ones here are local to `analytics/` and easy to change.

## Assumed table shape [reconcile-api]

The worker connects as `iw_app` and needs `SELECT` on `documents` and `SELECT, INSERT, UPDATE` on `findings`. It does not need `DELETE`.

`documents` (written by the scraper; read only here): `id uuid pk`, `source_id uuid`, `platform text`, `source_kind text`, `url text`, `canonical_url text null`, `fetched_at timestamptz`, `published_at timestamptz null`, `http_status int null`, `lang text null`, `title text null`, `text text`, `content_hash text`, `payload jsonb` (everything else in `ScrapedDocument`: `author`, `links`, `media`, `html_object_key`, `screenshots`, `blocks`, `scrape_meta`).

`findings` (written here, `status` updated by the API):

| Column | Type | Note |
|---|---|---|
| `id` | uuid pk | producer-generated uuid4 |
| `document_id` | uuid fk → documents | latest document |
| `module` | text | `M1`/`M2`/`M3` |
| `url_key` | text | `coalesce(canonical_url, url)` |
| `score` | double precision | 0-1 |
| `status` | text default `new` | owned by API after insert |
| `title`, `summary`, `content_excerpt` | text | |
| `url`, `platform` | text | denormalized |
| `firm`, `advertiser`, `rules`, `model` | jsonb | as in `Finding` |
| `source_fetched_at` | timestamptz | stale-write guard |
| `detected_at`, `updated_at` | timestamptz | |
| unique | `(url_key, module)` | upsert key |
| index | `(document_id)` | idempotency lookup |

If the API stores the finding as one `payload jsonb` instead, only the Postgres adapter changes. The specs do not.

## Assumed infra [reconcile-infra]

- Redis 7+ (XAUTOCLAIM needs ≥ 6.2) with AOF, reachable at `REDIS_URL`, and the network name analytics must join.
- `DATABASE_URL` uses the `iw_app` role. Secrets come from `.env` via `scripts/init-env.sh`.
- The root `compose.yaml` gets the line `- analytics/compose.yaml`.

## Risks / Trade-offs

- [Events lost between commit and publish, at most once] → the finding stays in the DB and the REST list. The outbox stays an open question. Log `publish_failed` with ids so an event can be replayed by hand in the demo.
- [Table shape differs from the API migration] → all SQL lives in one adapter class, the in-memory store carries the specs, and the Postgres tests run against the real migration once it exists.
- [Group starting at `0` replays a large backlog on the first start] → the idempotency check makes the replay cheap. The stream is small during the hackathon.
- [A pipeline bug acks real documents as `max_deliveries_exceeded`] → it is logged at `ERROR` with the traceback, and the document id can be re-XADDed after the fix.
- [`fakeredis` diverges from real Redis on XAUTOCLAIM] → one integration test against real Redis when `TEST_REDIS_URL` is set.

## Open Questions (for Damian)

1. **Re-scan events:** when a re-scan updates a finding, should analytics publish anything? Options: nothing (current spec); `finding.updated` `{id, status}`, which is valid but the schema meant it for status changes; or `finding.high_risk` when the new score crosses the threshold.
2. **Status on re-scan:** keep the analyst `status` (current spec), or reset `false_positive` / `closed` back to `new` when the score rises?
3. **Re-scan key:** is `coalesce(canonical_url, url)` right, or must it be exactly `url` ("a document from the same URL", plan §4)?
4. **Outbox vs at-most-once events:** accept losing an event on a crash between commit and publish for the hackathon, or add an `event_outbox` table (an API migration) now?
5. **Dead-letter stream:** poison messages are only logged and acked. Should they also go to `iw:documents:dead` for the demo or debugging?
6. **Test-only DDL:** until the API migration exists, may `analytics/tests/sql/schema.sql` (test fixture only, never run in compose) mirror the assumed tables so the Postgres adapter tests can run? Plan §12.4 item 1 suggested a temporary `analytics/sql/schema.sql`, and ADR 0303 since moved migrations to `api/`.
7. **Health port:** is a stdlib `/health` on 8001 inside `iw-data` enough, given that it is not routed through the gateway?
