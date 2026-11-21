# Tasks

Merge order: PR #18 (`chore/infra-compose-v2`) first, then PR #21. This branch merges `origin/chore/infra-compose-v2` (never a rebase) and merges it again when #18 gets new commits.

## 1. Stack on #18 and wire the api service (review items 1, 2, 3, 13)

- [x] 1.1 Merge `origin/chore/infra-compose-v2` into `api/api-v1-v2`, keeping both sides' `.env.example`, root `CLAUDE.md` and ADR-index entries; with a fresh `scripts/init-env.sh` `.env`, `docker compose config` fails on `REDIS_URL` (the review's reproduction)
- [x] 1.2 `api/compose.yaml`: `REDIS_URL` built from `REDIS_PASSWORD`, MinIO variables in #18's join-template form, `depends_on` `redis` (healthy) and `minio-init` (completed); `docker compose config` passes with the fresh `.env`
- [x] 1.3 Mutation check; config-only group: `mutations: n/a, compose values only (checked by docker compose config and the end-to-end run in 5.2)`

## 2. Calibration from analyst labels (review item 5)

- [x] 2.1 Failing tests for every "Calibration curve" scenario
- [x] 2.2 `GET /api/calibration` computes the curve from `confirmed`/`false_positive` findings and falls back to the latest stored run; the 2.1 tests and the contract response check pass
- [x] 2.3 Mutation check; mutations: 11 tried, 10 caught, 1 equivalent (reading the stored run even when labels exist changes no response, only adds a query)

## 3. Filter, trend, input and threshold fixes (review items 7, 8, 9, 10)

- [x] 3.1 Failing tests: "Whole first bucket", "Empty status list", NUL and length cases of "Invalid bodies", "URL kept as sent", "NUL in a text field", "Out-of-range value in the key", "No Redis round trip right after a failure"
- [x] 3.2 Fixes in `routes/stats.py`, `routes/findings.py`, `models.py`, `thresholds.py`; the 3.1 tests and the full suite pass
- [x] 3.3 Mutation check; mutations: 12 tried, 12 caught

## 4. Docs (review items 4, 6, 11, 12)

- [x] 4.1 `.docs/integration-plan.md`: the scraper owns the `iw:scan-requests` consumer group and publishes `scan.started`/`scan.finished`; `queries/__init__.py` docstring and the `errors.py` 500-handler comment match the code
- [x] 4.2 Damian's `.docs/STATUS.md` row (PR #21 stacked on #18) and the `.docs/INDEX.md` route for REST and Socket.IO; `api/README.md` calibration and input rules; `follow-ups.md` rows for the scan consumer, CI database services and the trend default window
- [x] 4.3 Mutation check; docs-only group: `mutations: n/a, docs only`

## 5. Closing

- [x] 5.1 Full suite on a throwaway Postgres 17 and Redis, docs-check, `openspec validate --all --strict`, test-diff-check, `pip-audit`
- [x] 5.2 End-to-end through the gateway on the stacked compose (#18 + this branch) with a fresh `scripts/init-env.sh`: `docker compose up` passes interpolation, `api` is healthy, and the end-to-end steps pass
- [x] 5.3 Apply the `iw-docs-update` skill (docs, Damian's STATUS row) and add the `iw-ai-log` row
- [x] 5.4 Run the `iw-pr-review` skill with one reviewer pass and fix real findings (URL validator hardened; mutations: 4 tried, 4 caught)
