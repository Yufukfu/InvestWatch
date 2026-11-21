# Status: platform (Damian)

Covers `analytics/`, `api/` and `contracts/`. Edit only this file for their state. Last updated: 2026-11-21 (Sat).

## State

### contracts
- v1 in `contracts/`, required core frozen; ADRs 0301-0305 accepted (PR #3).
- Mock server for `web/` in `contracts/mock-server/` (REST `http://localhost:8000/api`, Socket.IO `/events`) merged (PR #8, `mock-server` archived).

### analytics
- `analytics-skeleton` merged (PR #10): pure pipeline, registry, M2 rules R1-R3, CLI. No worker, storage or events yet.
- Both of Kacper's reviews fixed in `analytics-skeleton-review-fixes` and `analytics-skeleton-review-2-fixes`.
- `analytics-worker` implemented, PR #26 (base `main`, after PR #18 brought Redis): stream worker on `iw:documents` (ack after commit, XAUTOCLAIM, poison messages acked with a reason, backoff on outages), Postgres store with the `(document_id, module)` upsert, `iw:events` publisher with live thresholds, `/health`, container and compose service. Verified end to end on a full stack. Rules-only; the LLM client comes with `analytics-llm-p0`.
- `analytics-m1-m3` implemented (stage 2, stacked on PR #26): rules-only M1 (S1.1-S1.7, an inventory of third-party ads of registered firms) and M3 (S3.1-S3.8, offers that may indicate investment advice, the S3.4 gate at 0.4), routing by publisher and registry (a firm's own account to M2, unregistered own pages to M3, M1 plus M3 when the advice is the publisher's), `advertiser` on findings. The LLM wiring for M1/M3 is a follow-up change after `analytics-llm-p0`. The registry is still the fictional seed until the real KNF loader lands. Open: a re-scan that changes a document's module keeps the old finding (follow-up: mark superseded findings in the API/UI).
- `analytics-m1-m3-review-fixes`: Kacper's review of PR #35 fixed (registry "not found" wording with a demo-data flag, no bare `partner` label, no platform as advertiser, the challenge's M3 vocabulary and English pricing, Polish filter only for foreign firms without a branch, "możliwe"/"wspomina" titles, excerpt around the evidence, ADR 0308 for the S3.4 gate). The `_BOUNDARY` ReDoS comes with #26.
- Registry caveat: the default registry is the fictional `analytics/registry/seed.csv` (4 fictional firms). Until a real KNF registry is loaded and `REGISTRY_CSV` is set, R1 results and high-risk alerts for real firms are not meaningful; the worker logs `registry_seed` at startup. A real KNF loader is open (follow-up of `analytics-worker-review-fixes`).

### api
- `api-db-schema` applied and archived: Alembic `0001`-`0003` for `sources`, `documents`, `findings`, `job_errors`, `calibration_points`; one-shot `api-migrate` in the root stack.
- Merged with PR #15 (Kacper's review fixed in `api-db-schema-review-fixes`).
- `api-v1` applied and archived: REST under `/api` (all 11 contract paths), Socket.IO relay `iw:events` → `/events`, calibration curve from analyst labels, the `api` service in `api/compose.yaml`.
- In PR #21, stacked on PR #18 (`infra-compose`) and merging after it; Kacper's review fixed in `api-v1-review-fixes`.
- Open for Adam: nothing consumes `iw:scan-requests` yet, so `POST /api/scans` queues without running a scan (`.docs/integration-plan.md` §5).

### infra-compose
- Redis 8, object storage (MinIO, bucket `iw-raw`), the optional Ollama profile `llm`, project-scoped networks (`data`, `edge`, `egress`) and the smoke test `infra/tests/smoke.sh`: applied and archived, in PR #18.
- Kacper's two reviews of PR #18 fixed in `infra-compose-review-fixes` (archived).
- Follow-up: `OLLAMA_CONTEXT_LENGTH=8192` on the `ollama` service for the stage-2 LLM change (`infra-compose-review-fixes` follow-up 3).

## Active OpenSpec changes

- `api-v1` and `api-v1-review-fixes` archived in PR #21 (merges after PR #18)
- `api-db-schema` and `api-db-schema-review-fixes` archived in PR #15
- `infra-compose` and `infra-compose-review-fixes` archived in PR #18
- `analytics-worker` archived; `analytics-worker-review-fixes` (Kacper's PR #26 review) in PR #26
- `openspec-strict-format` archived in its own PR: 14 requirements across `database-schema`, `document-analysis`, `m2-compliance-rules`, `rest-api` and `shared-infrastructure` brought under OpenSpec 2.1.1's 500-character limit (text moved into scenarios, no behaviour change), so the CI job `Specs and hooks` passes. Its follow-ups name the fixes still due on `analytics-llm-p0` and `analytics-m1-m3`.

## Blockers and open decisions

- Contracts v1: the required core is frozen and accepted by Adam and Kacper ([ADR 0301](../decisions/0301-contracts-v1.md)). Optional fields, notably rendering metadata (`blocks`, screenshots), stay provisional until Integration #1 (Sat 17:00) and are still to be settled with Adam.
- Closed: the Alembic migration for the `documents` dedup index, `job_errors` and the published marker (`stream_published_at`) is Damian's ([ADR 0303](../decisions/0303-database-schema-ownership.md)) and is written: `api-db-schema`, PR #15.
