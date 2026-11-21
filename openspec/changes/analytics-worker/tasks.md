# Tasks

Precondition: `analytics-skeleton` is merged and this branch is rebased on it. Groups 1 and 3 need no infra. Group 2 waits for the final `api-db-schema` columns, which the coordinator forwards. Group 5 waits for `infra-compose`.

## 1. Config and store interface with the in-memory store

- [x] 1.1 Failing tests for the `finding-storage` scenarios on the in-memory store: load (payload merge, unknown id, invalid row naming the field), atomic save, first analysis, same document analysed again keeping `id`/`detected_at`/`status`/`note`, changed page as a new finding, different module, contract-valid read-back (skipped without `CONTRACTS_DIR`)
- [x] 1.2 `config.py` additions (`DATABASE_URL`, `REDIS_URL`, `WORKER_CONSUMER`, `STREAM_BLOCK_MS`, `CLAIM_MIN_IDLE_MS`, `MAX_DELIVERIES`, `HEALTH_PORT`), `storage.py` with the `Store` protocol, the error types `NotFound` / `InvalidDocument` / `StoreUnavailable`, `SaveResult` (`created` / `updated`) and `InMemoryStore`; tests green
- [x] 1.3 Mutation check; `mutations: 16 tried, 16 caught` (the lock mutant first survived; the in-memory store got a `before_commit` test seam so the concurrent test really interleaves)

## 2. Postgres store

- [ ] 2.1 Reconcile the assumed `documents` / `findings` columns and grants with the final `api-db-schema` migration (design "Assumed table shape"); record the result in `design.md`; write `analytics/tests/sql/schema.sql` mirroring that migration, with a header naming the source revision and saying it is test-only
- [ ] 2.2 Failing test: the group 1 scenario suite parametrized over `PostgresStore` (skipped without `TEST_DATABASE_URL`; the fixture applies `tests/sql/schema.sql`), plus concurrent upsert to one row (one `created`, one `updated`), and connection refused raising `StoreUnavailable` with no partial write
- [ ] 2.3 `PostgresStore` (psycopg 3, one transaction per save, the `ON CONFLICT (document_id, module) DO UPDATE` statement from `api-db-schema`'s `findings_upsert()`, `RETURNING id, xmax = 0`); pin `psycopg[binary]`; tests green; `pip-audit -r analytics/requirements.txt` clean
- [ ] 2.4 Mutation check; `mutations: N tried, N caught`

## 3. Events and thresholds

- [x] 3.1 Failing tests for the `finding-events` scenarios with `fakeredis`: envelope validates against `events.schema.json` (skipped without `CONTRACTS_DIR`), no `risk_level`, persisted id, created-only below the threshold, created then high_risk at an equal score, nothing on update, event id taken from the save result, live threshold change, key missing / malformed falling back to defaults with the logged reason, `publish_failed` on a connection error, no-op publisher records the same events
- [x] 3.2 `events.py`: `Publisher` protocol, `RedisPublisher`, `NoopPublisher`, `read_thresholds()` with no cache; pin `redis`, dev `fakeredis`; tests green
- [x] 3.3 Mutation check; `mutations: 23 tried, 23 caught` (the channel-name mutant first survived; a literal contract-name test was added)

## 4. Worker loop

- [ ] 4.1 Failing tests for the `document-stream-worker` scenarios with `fakeredis`, `InMemoryStore` and `NoopPublisher`: group creation (new and BUSYGROUP, backlog from `0`), happy-path order commit → publish → XACK, no findings, crash before XACK redelivered and saved as `updated` with no event, duplicate delivery and re-analysis after a re-XADD, each poison reason, `max_deliveries_exceeded` at the limit only, poison followed by a valid message, XAUTOCLAIM stale vs not stale, store outage leaving the message pending then succeeding, Redis outage backoff without exit, missing `DATABASE_URL` exits non-zero, `model.llm` null, one JSON outcome line per message, SIGTERM finishing the current message
- [ ] 4.2 `worker.py` (`python -m investwatch_analytics.worker`): startup (config, registry, catalogue, group), loop, ack policy, capped backoff with jitter, signal handling; tests green
- [ ] 4.3 One integration test against real Redis (`TEST_REDIS_URL`, skipped otherwise) covering XAUTOCLAIM and the delivery count
- [ ] 4.4 Mutation check; `mutations: N tried, N caught`

## 5. Health, container and compose

- [ ] 5.1 Reconcile Redis network name, `REDIS_URL` and the migration job name with `infra-compose` and the API change (design "Assumed infra"); record in `design.md`
- [ ] 5.2 Failing tests: `/health` 200 with both up, 503 with `"db": false` when the store is down, 503 with `"redis": false` when Redis is down
- [ ] 5.3 `health.py` (stdlib `http.server` thread); `analytics/Dockerfile` (`public.ecr.aws/docker/library/python:3.13-slim`, uid 10001, HEALTHCHECK), `.dockerignore`, `analytics/compose.yaml` (hardened like `web/compose.yaml`), one `include:` line in the root `compose.yaml` (announced to B), `.env.example` additions; tests green
- [ ] 5.4 Manual check: `docker build` succeeds, `id -u` in the image is not 0, `docker compose up --build` makes `analytics` healthy, and an `XADD iw:documents * document_id <mock id> schema v1` for a seeded mock document yields a `findings` row and a `finding.created` message seen with `SUBSCRIBE iw:events`
- [ ] 5.5 Mutation check; `mutations: n/a, container and compose config` unless 5.3 adds logic beyond `health.py`, in which case `mutations: N tried, N caught`

## 6. Closing

- [ ] 6.1 Apply the iw-docs-update skill (`analytics/README.md` run and env section, `analytics/CLAUDE.md` if a rule is easy to get wrong, the analytics row of `.docs/STATUS.md`, `docs-check` clean) and add the iw-ai-log row
- [ ] 6.2 Run the iw-pr-review skill and fix real findings
