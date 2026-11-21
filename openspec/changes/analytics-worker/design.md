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
2. **Processing order: load, analyze, save (one transaction, commit), publish, XACK.** This is the only order in which an acknowledged message implies durable findings. The cost is that events are at most once: a crash between commit and publish loses them. The finding is still in the DB, and the dashboard's REST list shows it. Alternative: an outbox table with a relay. It is the correct fix but needs a migration in `api/` and a second loop, so it is deferred (coordinator decision: at most once for the hackathon).
3. **Idempotency through the upsert, no pre-check.** A redelivered or re-sent message is analysed again and saved through the `(document_id, module)` upsert. Its findings come back `updated`, and `updated` publishes nothing, so a duplicate delivery changes no ids, statuses or events. Rules-only analysis is cheap, so re-running it costs nothing that matters. It also lets a manual re-XADD refresh a finding after a rule fix. Alternative: skip the message when findings for the `document_id` exist. Rejected because it blocks re-analysis and adds a query. A processed-ids set in Redis was also rejected, because it can disagree with the DB after a failed commit.
4. **Finding identity `(document_id, module)`, as `api-db-schema` defines it** (coordinator decision, replacing the earlier URL-based key). The upsert is `INSERT ... ON CONFLICT (document_id, module) DO UPDATE SET score, title, summary, firm, advertiser, rules, content_excerpt, url, platform, model, updated_at = EXCLUDED.* RETURNING id, (xmax = 0) AS created`. The same statement is documented in `api-db-schema` as `findings_upsert()`, which analytics copies. It never touches `id`, `detected_at`, `status` or `note`, because analysts own `status` and `note` (`PATCH /findings/{id}`). The unique key makes concurrent workers safe. A changed page is a new `documents` row (new `content_hash`, scraper dedup on `(source_id, content_hash)`), so it gets a new finding by design. An unchanged page is dropped by the scraper's dedup and never reaches analytics. No stale-write guard is needed, because an older document only ever updates its own finding.
5. **Error taxonomy drives ack/no-ack.** The store and the loader raise `NotFound`, `InvalidDocument` (wrapping Pydantic's error and naming the field) or `StoreUnavailable` (connection loss, `SerializationFailure`, `OperationalError`). `NotFound` and `InvalidDocument` are acked as poison. `StoreUnavailable` and Redis `ConnectionError` cause backoff and no ack. Any other exception is a suspected bug: the message is left pending, and once its delivery count (from `XPENDING` / the XAUTOCLAIM entry) reaches `MAX_DELIVERIES` it is acked as `max_deliveries_exceeded`, with the traceback logged. Backoff is capped exponential (1, 2, 4 … 30 s) with jitter.
6. **XAUTOCLAIM every loop iteration, with `COUNT 10` and `JUSTID` off.** It is cheap and reclaims both this consumer's own pending entries after a restart and those of a dead consumer. The group is created with `XGROUP CREATE iw:documents analytics 0 MKSTREAM`, and `BUSYGROUP` is ignored. Starting at `0` instead of `$` means documents the scraper sent before analytics' first start are not lost, at the cost of one full pass over the stream backlog on the very first start.
7. **Threshold read per finding, no cache.** `GET iw:settings:thresholds` returns a Redis string holding a JSON object such as `{"M1":0.6,"M2":0.5,"M3":0.7}`, matching the REST `Thresholds` schema (`contracts/openapi.yaml`). The API writes it (ADR 0305; format confirmed by the coordinator). Invalid or missing values fall back per module to 0.6 / 0.5 / 0.7. One GET per new finding is negligible.
8. **Events are built from the save result,** so the `id` is the stored row's id, also when a concurrent save won the insert. The publisher serializes the `event` envelope with `emitted_at = now()` and no `risk_level`. Tests validate it against `events.schema.json` when `CONTRACTS_DIR` is set, the same skip rule as the skeleton's contract tests.
9. **Document loading:** `SELECT` the simple columns plus `payload`, merge them as `{**payload, **columns}`, then `ScrapedDocument.model_validate`. Columns win, because they are what the scraper indexes and deduplicates on.
10. **`/health` with stdlib `http.server` in a daemon thread.** It is the convention every service follows (§7) without pulling in a web framework. It pings Redis and runs `SELECT 1` with a 1 s timeout. The Docker HEALTHCHECK calls it with `python -c` (the slim image has no curl).
11. **Container.** The Dockerfile is `public.ecr.aws/docker/library/python:3.13-slim` (infra rule: images from the ECR mirror). It installs pinned requirements first for layer caching, copies `src/` and `registry/`, creates user `iw` (uid 10001) and sets `USER 10001`. The entrypoint is `python -m investwatch_analytics.worker`. `analytics/compose.yaml` follows `web/compose.yaml`: `read_only: true`, `tmpfs /tmp`, `cap_drop: [ALL]`, `no-new-privileges`, CPU and memory limits, the networks `iw-data` (Postgres) and Redis's network **[reconcile-infra]**, and `depends_on` on healthy Postgres and Redis plus `api-migrate: {condition: service_completed_successfully}` (the one-shot Alembic job in `api/compose.yaml`). `iw-data` is internal, so a hosted LLM later needs an egress network. That is not needed in this change. The skeleton targets `>=3.12`, and the image pins 3.13.
12. **Config additions** in `config.py`, all env-only: `DATABASE_URL` and `REDIS_URL` (required for the worker, not for the CLI), `WORKER_CONSUMER` (default hostname), `STREAM_BLOCK_MS` (5000), `CLAIM_MIN_IDLE_MS` (60000), `MAX_DELIVERIES` (5) and `HEALTH_PORT` (8001). Stream, group, channel and key names are contract constants in code, not env.

No ADR: the irreversible choices (schema ownership, threshold storage, event producer) are already ADRs 0303 and 0305. The ones here are local to `analytics/` and easy to change.

## Table shape (reconciled with api-db-schema)

Reconciled in task 2.1 against `api-db-schema` on branch `api/api-v1` at `1be0451`: Alembic revisions `0001_initial` and `0002_query_indexes`, the SQL section of the api README and `findings_upsert()` in the api package's `db/sql.py` (both on that branch). `analytics/tests/sql/schema.sql` mirrors the three tables analytics touches (`sources`, `documents`, `findings`) for the Postgres store tests only. The migration stays the source of truth.

The worker connects as `iw_app` (`infra/postgres/init/01-app-role.sh` grants CRUD on tables `iw_admin` creates). It reads `documents` and inserts or updates `findings`. It never deletes, and never writes `status` or `note`.

`documents` (written by the scraper; read only here): scalar columns `id, source_id, platform, source_kind, url, canonical_url, fetched_at, published_at, http_status, lang, title, text, content_hash, html_object_key`, plus `payload jsonb` (`author, links, media, screenshots, blocks, scrape_meta`), `stream_published_at` and `created_at`, which are not read here. The loader merges the scalar columns over `payload`. Because of `NOT NULL` on `text`, the CHECKs on `platform`, `source_kind`, `lang` and `content_hash`, and `payload` being an object, an invalid document in the database can only be a value the schema does not constrain: a non-http(s) `url`, or a malformed nested object in `payload`.

`findings` (written here; `status` and `note` updated by the API): `id, document_id → documents (ON DELETE CASCADE), module, score, status default 'new', title, summary, firm jsonb, advertiser jsonb, rules jsonb default '[]', content_excerpt (≤ 500), url, platform, note, detected_at, updated_at, model jsonb`. Constraint `uq_findings_document_module (document_id, module)`. There is no `risk_level`. The upsert is the README statement verbatim: `ON CONFLICT ON CONSTRAINT uq_findings_document_module DO UPDATE SET score, title, summary, firm, advertiser, rules, content_excerpt, url, platform, model, updated_at = excluded.*`, with `RETURNING ..., (xmax = 0) AS inserted` to tell `created` from `updated`. `advertiser` is written as null until the `Finding` model carries it (follow-up 3).

Postgres store details: one connection per thread (`autocommit` plus an explicit transaction per save), reopened on the next call after an `OperationalError`. `SerializationFailure` and `DeadlockDetected` are `StoreUnavailable` but keep the connection. Any other driver error (an FK violation for a missing document, a missing grant, a `DataError`) is a plain `StoreError` carrying only the class and SQLSTATE, because driver messages can echo row values. Connection errors keep the class and the first libpq line. A `DATABASE_URL` libpq cannot parse raises `StoreMisconfigured` at construction, with no chained exception, because libpq quotes the bad token and that token may be the password.

## Assumed infra [reconcile-infra]

- Redis 7+ (XAUTOCLAIM needs ≥ 6.2) with AOF, reachable at `REDIS_URL`, and the network name analytics must join.
- `DATABASE_URL` uses the `iw_app` role. Secrets come from `.env` via `scripts/init-env.sh`.
- The root `compose.yaml` gets the line `- analytics/compose.yaml`.

## Risks / Trade-offs

- [Events lost between commit and publish, at most once] → the finding stays in the DB and the REST list. No outbox for the hackathon. Log `publish_failed` with ids so an event can be replayed by hand in the demo.
- [Table shape differs from the API migration] → all SQL lives in one adapter class, the in-memory store carries the specs, and the Postgres tests run against the real migration once it exists.
- [Group starting at `0` replays a large backlog on the first start] → the replay is rules-only and the upsert publishes nothing for documents already analysed. The stream is small during the hackathon.
- [A pipeline bug acks real documents as `max_deliveries_exceeded`] → it is logged at `ERROR` with the traceback, and the document id can be re-XADDed after the fix.
- [`fakeredis` diverges from real Redis on XAUTOCLAIM] → one integration test against real Redis when `TEST_REDIS_URL` is set.

## Resolved questions

Decided by the coordinating session on Damian's instruction to coordinate the OpenSpec work (2026-11-21). Damian can override them.

1. **Events on an update:** nothing is published when a finding is `updated`.
2. **Status on re-analysis:** the analyst's `status` and `note` are kept.
3. **Finding key:** `(document_id, module)` from `api-db-schema`, not a URL key. A changed page gets a new finding.
4. **Outbox:** none. Events are at most once.
5. **Dead-letter stream:** none. Poison messages are logged and acked.
6. **Test-only DDL:** yes. `analytics/tests/sql/schema.sql` mirrors the `api-db-schema` migration columns from branch `api/api-v1`, says so in its header, and is never run in compose.
7. **Health:** a stdlib `/health` on 8001 inside `iw-data` is enough.
8. **Threshold key format:** a Redis string with JSON `{"M1":0.6,"M2":0.5,"M3":0.7}`, written by the API. A missing key or module falls back to the ADR 0305 defaults.

## Open Questions

- Whether a re-analysis with a much higher score should reopen a `closed` or `false_positive` finding. This is a product rule, also open in `api-db-schema`. Until it is answered, the status is kept.
