# Tasks

Precondition: `analytics-skeleton` is merged (PR #10, `main` 2f1a66a) and this branch is rebased on `origin/main`. Groups 1 and 3 need no infra. Group 2 is reconciled with `api-db-schema` as merged on `main` (`fea7ef1`, PR #15). Group 5 is reconciled with infra-compose (PR #18, verified on a scratch stack of `chore/infra-compose-v2` + `api/` + this `analytics/`) and `api/compose.yaml` (on `main`); this branch merges after PR #18.

## 1. Config and store interface with the in-memory store

- [x] 1.1 Failing tests for the `finding-storage` scenarios on the in-memory store: load (payload merge, unknown id, invalid row naming the field), atomic save, first analysis, same document analysed again keeping `id`/`detected_at`/`status`/`note`, changed page as a new finding, different module, contract-valid read-back (skipped without `CONTRACTS_DIR`)
- [x] 1.2 `config.py` additions (`DATABASE_URL`, `REDIS_URL`, `WORKER_CONSUMER`, `STREAM_BLOCK_MS`, `CLAIM_MIN_IDLE_MS`, `MAX_DELIVERIES`, `HEALTH_PORT`), `storage.py` with the `Store` protocol, the error types `NotFound` / `InvalidDocument` / `StoreUnavailable`, `SaveResult` (`created` / `updated`) and `InMemoryStore`; tests green
- [x] 1.3 Mutation check; `mutations: 16 tried, 16 caught` (the lock mutant first survived; the in-memory store got a `before_commit` test seam so the concurrent test really interleaves)

## 2. Postgres store

- [x] 2.1 Reconcile the assumed `documents` / `findings` columns and grants with the final `api-db-schema` migration (design "Assumed table shape"); record the result in `design.md`; write `analytics/tests/sql/schema.sql` mirroring that migration, with a header naming the source revision and saying it is test-only
- [x] 2.2 Failing test: the group 1 scenario suite parametrized over `PostgresStore` (skipped without `TEST_DATABASE_URL`; the fixture applies `tests/sql/schema.sql`), plus concurrent upsert to one row (one `created`, one `updated`), and connection refused raising `StoreUnavailable` with no partial write
- [x] 2.3 `PostgresStore` (psycopg 3, one transaction per save, the `ON CONFLICT (document_id, module) DO UPDATE` statement from `api-db-schema`'s `findings_upsert()`, `RETURNING id, xmax = 0`); pin `psycopg[binary]`; tests green; `pip-audit -r analytics/requirements.txt` clean
- [x] 2.4 Mutation check; `mutations: 15 tried, 15 caught` (run against a throwaway Postgres 17 on 127.0.0.1:55433; three first survived and got tests: firm JSON round trip, a dropped still-open connection, a kept connection on a conflict). After the iw-reviewer fixes (malformed `DATABASE_URL` raises `StoreMisconfigured` without quoting it, other driver errors become a detail-free `StoreError`, dropped connections are forgotten, non-UUID `findings_for_document` returns `[]`): `mutations: 8 tried, 8 caught`; the redundant `IntegrityError` branch was removed

## 3. Events and thresholds

- [x] 3.1 Failing tests for the `finding-events` scenarios with `fakeredis`: envelope validates against `events.schema.json` (skipped without `CONTRACTS_DIR`), no `risk_level`, persisted id, created-only below the threshold, created then high_risk at an equal score, nothing on update, event id taken from the save result, live threshold change, key missing / malformed falling back to defaults with the logged reason, `publish_failed` on a connection error, no-op publisher records the same events
- [x] 3.2 `events.py`: `Publisher` protocol, `RedisPublisher`, `NoopPublisher`, `read_thresholds()` with no cache; pin `redis`, dev `fakeredis`; tests green
- [x] 3.3 Mutation check; `mutations: 23 tried, 23 caught` (the channel-name mutant first survived; a literal contract-name test was added). After the iw-reviewer fixes (GETs counted on the client, partial publish, `url`/`platform` replaced on update): `mutations: 8 tried, 8 caught`

## 4. Worker loop

- [x] 4.1 Failing tests for the `document-stream-worker` scenarios with `fakeredis`, `InMemoryStore` and `NoopPublisher`: group creation (new and BUSYGROUP, backlog from `0`), happy-path order commit → publish → XACK, no findings, crash before XACK redelivered and saved as `updated` with no event, duplicate delivery and re-analysis after a re-XADD, each poison reason, `max_deliveries_exceeded` at the limit only, poison followed by a valid message, XAUTOCLAIM stale vs not stale, store outage leaving the message pending then succeeding, Redis outage backoff without exit, missing `DATABASE_URL` exits non-zero, `model.llm` null, one JSON outcome line per message, SIGTERM finishing the current message
- [x] 4.2 `worker.py` (`python -m investwatch_analytics.worker`): startup (config, registry, catalogue, group), loop, ack policy, capped backoff with jitter, signal handling; tests green
- [x] 4.3 One integration test against real Redis (`TEST_REDIS_URL`, skipped otherwise) covering XAUTOCLAIM and the delivery count
- [x] 4.4 Mutation check; `mutations: 27 tried, 27 caught` (two first survived and got tests: an outage during the save, a stopped worker making no Redis calls). The real-Redis test ran against a throwaway `redis:7-alpine` on 127.0.0.1:56380. After the iw-reviewer fixes (stop cuts a backoff short, malformed `REDIS_URL` exits 2, `NOGROUP` recreates the group, other `ResponseError`s back off, the real-Redis test checks the delivery count): `mutations: 5 tried, 5 caught`

## 5. Health, container and compose

- [x] 5.1 Reconcile Redis network name, `REDIS_URL` and the migration job name with `infra-compose` and the API change (design "Assumed infra"); record in `design.md`
- [x] 5.2 Failing tests: `/health` 200 with both up, 503 with `"db": false` when the store is down, 503 with `"redis": false` when Redis is down
- [x] 5.3 `health.py` (stdlib `http.server` thread); `analytics/Dockerfile` (`public.ecr.aws/docker/library/python:3.13-slim`, uid 10001, HEALTHCHECK), `.dockerignore`, `analytics/compose.yaml` (hardened like `web/compose.yaml`), one `include:` line in the root `compose.yaml` (announced to B), `.env.example` additions; tests green
- [x] 5.4 Manual check: `docker build` succeeds, `id -u` in the image is not 0, `docker compose up --build` makes `analytics` healthy, and an `XADD iw:documents * document_id <mock id> schema v1` for a seeded mock document yields a `findings` row and a `finding.created` message seen with `SUBSCRIBE iw:events`
- [x] 5.5 Mutation check; `mutations: 11 tried, 11 caught` (`health.py` 6/6; the SIGTERM path 5/5, where two first survived: `StopRequested` became a `BaseException` and the handler install got a test). Dockerfile and compose are config: `mutations: n/a, config only`, verified by 5.4 instead. After the iw-reviewer fixes (health ping on a short-lived connection, a taken `HEALTH_PORT` exits 2, only the first signal raises, base image pinned by digest): `mutations: 3 tried, 3 caught`

## 7. Advertiser on `Finding` (issue #20, follow-up 3)

Done between groups 4 and 5 at the owner's request, so the PR ships the full `UPSERT_REPLACED` list. M2 sets no advertiser; M1/M3 will.

- [x] 7.1 Failing tests: `AdvertiserRef` in contract shape (strict, `in_registry` required, absolute http(s) URLs), `Finding.advertiser` defaults to `None`, the store replaces `advertiser` on update and reads it back on both backends, absent `advertiser` is SQL `NULL`
- [x] 7.2 `AdvertiserRef` and `Finding.advertiser` in `models.py`; `advertiser` in `ANALYSIS_FIELDS` and `FINDING_COLUMNS`, the upsert `SET` list built from `ANALYSIS_FIELDS`; full suite green (with `TEST_DATABASE_URL` and `CONTRACTS_DIR`)
- [x] 7.3 Mutation check; `mutations: 8 tried, 8 caught` (throwaway Postgres 17 on 127.0.0.1:55437)

## 6. Closing

- [ ] 6.1 Apply the iw-docs-update skill (already added: the `iw:events` envelope rule in `analytics/CLAUDE.md` and `.docs/analytics-plan.md` §12.2, asked for by the api-v1 session; `analytics/README.md` run and env section, `analytics/CLAUDE.md` if a rule is easy to get wrong, the `### analytics` section of `.docs/status/platform.md` (ADR 0205: `.docs/STATUS.md` is team milestones only), `docs-check` clean) and add the iw-ai-log row
- [ ] 6.2 Run the iw-pr-review skill and fix real findings
