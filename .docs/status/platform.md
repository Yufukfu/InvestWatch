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
- `analytics-m1-m3-review-2-fixes`: Kacper's second review of PR #35 fixed (the page host through `http_host` in `registry.match`, so a backslash URL is no firm's page; a 200 KB scan cap for routing and M1/M3; a handle alone is not a firm's account; names matched after NFKC and zero-width removal; growth-checked ReDoS tests). Real-scale registry matching comes with the stage-3 `analytics-knf-registry` change.
- `analytics-knf-registry` implemented (stage 3, stacked on PR #35): the default registry is the real KNF register `analytics/registry/knf.csv` (749 firms from the four lists of annexes 1/2, snapshot 2026-11-21T20:49:58Z, ADR 0311), refreshed only by hand with `python -m investwatch_analytics.knf`; the worker logs `registry_loaded` with the snapshot date; R1 passes only on the official name (an alias alone is `uncertain`); real-scale matching (749 firms: a few ms for a typical page, under 0.5 s for a 200 KB page of varied words). Waiting for Damian: the 31 curated domains in `analytics/registry/knf_domains_manual.csv` are all `verified_by_human=false`; 7 Polish firms have no curated domain because their sites could not be verified (Aixon Investment Management, Dom Inwestycyjny Nehrebetius, PGE Dom Maklerski, Everest Investment Management, Doradztwo dla Polskich Przedsiębiorstw Securities, IFDS Dom Maklerski, LFI Dom Maklerski). `seed.csv` (4 fictional firms) stays the test fixture.

### api
- `api-db-schema` applied and archived: Alembic `0001`-`0003` for `sources`, `documents`, `findings`, `job_errors`, `calibration_points`; one-shot `api-migrate` in the root stack.
- Merged with PR #15 (Kacper's review fixed in `api-db-schema-review-fixes`).
- `api-v1` applied and archived: REST under `/api` (all 11 contract paths), Socket.IO relay `iw:events` → `/events`, calibration curve from analyst labels, the `api` service in `api/compose.yaml`.
- In PR #21, stacked on PR #18 (`infra-compose`) and merging after it; Kacper's review fixed in `api-v1-review-fixes`.
- Open for Adam: nothing consumes `iw:scan-requests` yet, so `POST /api/scans` queues without running a scan (`.docs/integration-plan.md` §5).

### infra-compose
- Redis 8, object storage (MinIO, bucket `iw-raw`), the optional Ollama profile `llm`, project-scoped networks (`data`, `edge`, `egress`) and the smoke test `infra/tests/smoke.sh`: applied and archived, in PR #18.
- Kacper's two reviews of PR #18 fixed in `infra-compose-review-fixes` (archived).
- `OLLAMA_CONTEXT_LENGTH=8192` (default, override in `.env`) on the `ollama` service for the stage-2 LLM change: issue #32, branch `chore/ollama-context-length` (`infra-compose-review-fixes` follow-up 3).

## Active OpenSpec changes

- `api-v1` and `api-v1-review-fixes` archived in PR #21 (merges after PR #18)
- `api-db-schema` and `api-db-schema-review-fixes` archived in PR #15
- `infra-compose` and `infra-compose-review-fixes` archived in PR #18
- `analytics-worker` archived; `analytics-worker-review-fixes` (Kacper's PR #26 review) in PR #26
- `openspec-strict-format` archived in its own PR: 14 requirements across `database-schema`, `document-analysis`, `m2-compliance-rules`, `rest-api` and `shared-infrastructure` brought under OpenSpec 2.1.1's 500-character limit (text moved into scenarios, no behaviour change), so the CI job `Specs and hooks` passes. Its follow-ups name the fixes still due on `analytics-llm-p0` and `analytics-m1-m3`.

## Blockers and open decisions

- Contracts v1: the required core is frozen and accepted by Adam and Kacper ([ADR 0301](../decisions/0301-contracts-v1.md)). Optional fields, notably rendering metadata (`blocks`, screenshots), stay provisional until Integration #1 (Sat 17:00) and are still to be settled with Adam.
- Closed: the Alembic migration for the `documents` dedup index, `job_errors` and the published marker (`stream_published_at`) is Damian's ([ADR 0303](../decisions/0303-database-schema-ownership.md)) and is written: `api-db-schema`, PR #15.
