# Status: platform (Damian)

Covers `analytics/`, `api/` and `contracts/`. Edit only this file for their state. Last updated: 2026-11-22 (Sun).

## State

### contracts
- v1 in `contracts/`, required core frozen; ADRs 0301-0305 accepted (PR #3).
- Mock server for `web/` in `contracts/mock-server/` (REST `http://localhost:8000/api`, Socket.IO `/events`) merged (PR #8, `mock-server` archived).
- Contract 1.1.0 (`findings-document-filter`, issue #33, team OK): optional `document_id` on `GET /findings` in the contract, `api/` and the mock server, plus a mock post with an M1 and an M3 finding. Kacper re-syncs `web/`'s contract snapshot in his PR.

### analytics
- `analytics-post-integration-fixes` (from the 2026-11-21/22 end-to-end runs): pages on `knf.gov.pl`/`gov.pl` route to no module (`official_source`, `OFFICIAL_SOURCE_DOMAINS`); an M3-only document needs an offer signal (S3.3/S3.4/S3.5/S3.8), so service vocabulary alone (EY negative control) is `no_signals`; preprocessing normalizes once. Defaults unchanged; the LLM evaluation numbers went to Damian for a decision.
- `analytics-skeleton` merged (PR #10): pure pipeline, registry, M2 rules R1-R3, CLI. No worker, storage or events yet.
- Both of Kacper's reviews fixed in `analytics-skeleton-review-fixes` and `analytics-skeleton-review-2-fixes`.
- `analytics-worker` implemented, PR #26 (base `main`, after PR #18 brought Redis): stream worker on `iw:documents` (ack after commit, XAUTOCLAIM, poison messages acked with a reason, backoff on outages), Postgres store with the `(document_id, module)` upsert, `iw:events` publisher with live thresholds, `/health`, container and compose service. Verified end to end on a full stack. Rules-only; the LLM client comes with `analytics-llm-p0`.
- `analytics-m1-m3` implemented (stage 2, stacked on PR #26): rules-only M1 (S1.1-S1.7, an inventory of third-party ads of registered firms) and M3 (S3.1-S3.8, offers that may indicate investment advice, the S3.4 gate at 0.4), routing by publisher and registry (a firm's own account to M2, unregistered own pages to M3, M1 plus M3 when the advice is the publisher's), `advertiser` on findings. The LLM wiring for M1/M3 is a follow-up change after `analytics-llm-p0`. The registry is still the fictional seed until the real KNF loader lands. A re-scan that changes a document keeps the old finding; the API now marks it `changed` on the detail (`api-rescan-state`, issue #71).
- `analytics-m1-m3-review-fixes`: Kacper's review of PR #35 fixed (registry "not found" wording with a demo-data flag, no bare `partner` label, no platform as advertiser, the challenge's M3 vocabulary and English pricing, Polish filter only for foreign firms without a branch, "możliwe"/"wspomina" titles, excerpt around the evidence, ADR 0308 for the S3.4 gate). The `_BOUNDARY` ReDoS comes with #26.
- `analytics-m1-m3-review-2-fixes`: Kacper's second review of PR #35 fixed (the page host through `http_host` in `registry.match`, so a backslash URL is no firm's page; a 200 KB scan cap for routing and M1/M3; a handle alone is not a firm's account; names matched after NFKC and zero-width removal; growth-checked ReDoS tests). Real-scale registry matching comes with the stage-3 `analytics-knf-registry` change.
- `analytics-knf-registry` implemented (stage 3, stacked on PR #35): the default registry is the real KNF register `analytics/registry/knf.csv` (749 firms from the four lists of annexes 1/2, snapshot 2026-11-21T20:49:58Z, ADR 0311), refreshed only by hand with `python -m investwatch_analytics.knf`; the worker logs `registry_loaded` with the snapshot date; R1 passes only on the official name (an alias alone is `uncertain`); real-scale matching (749 firms: a few ms for a typical page, under 0.5 s for a 200 KB page of varied words). Waiting for Damian: the 31 curated domains in `analytics/registry/knf_domains_manual.csv` are all `verified_by_human=false`; 7 Polish firms have no curated domain because their sites could not be verified (Aixon Investment Management, Dom Inwestycyjny Nehrebetius, PGE Dom Maklerski, Everest Investment Management, Doradztwo dla Polskich Przedsiębiorstw Securities, IFDS Dom Maklerski, LFI Dom Maklerski). `seed.csv` (4 fictional firms) stays the test fixture.
- `analytics-llm-p0` implemented (stage 2, PR to `main`): the LLM layer and the M2 P0 rules.
  - Rules: R4 (risk font size), R6 (hidden risk, never `pass` on missing render metadata), R14 (past-performance disclaimer, amounts included), R17/R18 (supervisor mention, then its use), R3 near-window refinement.
  - LLM: an OpenAI-compatible client (httpx), delimited prompt, chunking, verified quotes, Redis cache, per-document budget and circuit breaker, wired into the worker and the CLI (`--no-llm`) and into M1/M3 (S1.4, S1.5, S3.3, S3.4).
  - Hosted default Gemma 4 on the Gemini API (ADR 0317). Measured on 2026-11-21: valid JSON after a `<thought>` strip; 15-30 s per call on `gemma-4-26b-a4b-it`; about half the calls returned 503 "high demand". The demo must not depend on it: pre-warm the cache, keep the Ollama profile ready.
  - R10 (language consistency) was cut and deferred (follow-ups R67).
  - The M2 default threshold was re-measured from 0.25 to 0.1 (ADR 0316 procedure).
  - Decided by Damian: the default model stays `gemma-4-31b-it` (`gemma-4-26b-a4b-it` is the documented fallback), and the M2 default 0.1 is accepted (ADR 0317). It is re-measured with the LLM after merge.
- `analytics-embeddings` implemented (stage 3, branch `analytics/analytics-embeddings`): embeddings client for local `bge-m3` (`EMBED_*`, Redis cache, breaker, `model.embedder`, ADR 0313); dictionary topic gate before the modules (`off_topic`, `iw:stats:gate`, `firm_own` never gated); MinHash near-dup groups in Redis with one `finding.high_risk` per group and module and a summary sentence naming the original (ADR 0314); own numpy MinHash instead of datasketch (which loads scipy, about 115 MB). Gate similarity to centroids is a stretch item, not built. Infra ask for Kacper: issue #65 (`bge-m3` in `ollama-pull`, `OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_KEEP_ALIVE`).
- `analytics/compose-single-build` (fix, no OpenSpec change): only `analytics` builds `investwatch/analytics`; `analytics-eval` reuses the image like `api` does with `api-migrate`, so `docker compose up --build` no longer aborts on two parallel exports to one tag ("image ... already exists" with the containerd store). The build context is `../analytics`, so the `-f infra/compose.yaml -f api/compose.yaml -f analytics/compose.yaml` command in the file header builds too (before, `.` resolved to `infra/`).
- `analytics/eval-wait-healthcheck` (fix, no OpenSpec change): `docker compose up -d --wait` exits 0 again. Before, it exited 1 with "analytics-eval has no healthcheck configured" although every service was healthy or exited 0. `--wait` checks a service nobody depends on for "running or healthy", which a one-shot fails either way: with `healthcheck: disable: true` it is "no healthcheck configured", and with no healthcheck it is "exited (0)" once the run has finished. `analytics` now depends on `analytics-eval` with `service_completed_successfully` and `required: false`, so `--wait` checks completion, as for `api-migrate`. The worker still starts if the evaluation fails, and `--wait` then exits 1 with "didn't complete successfully". The image `HEALTHCHECK` stays in `analytics/Dockerfile` as the `document-stream-worker` spec requires.
- `analytics-stored-content-hash` (issue #31, Damian's decision): analytics no longer computes a `content_hash` (`preprocess()` had an NFKC one, used only as the LLM cache key); it uses the stored NFC value the scraper writes as is, also for the LLM cache key, and a document without one is not cached ([ADR 0105](../decisions/0105-content-hash-normalisation.md)). NFKC `normalize()` stays for matching, language guess and excerpts. Open: `contracts/mocks/generate_mocks.py` still lowercases before hashing (`content-hash-definition` follow-up 4, Damian's own decision).
- Presentation (#77, #74): analytics slide content in `.docs/presentation-analytics.md` (rules-only gold-set numbers on the synthetic set, R14 add-a-rule example, LLM swap summary). Open: real UKNF samples (#73) and the Ollama rehearsal on the demo machine.

### rehearsal on real data (#78, 2026-11-22, `main` c810a14)
- Clean stack, 17 seeded sources, one scan request each: analytics handled all 223 documents (71 stored, 152 `no_findings`), 72 findings, 10 `finding.high_risk` events (equal to the findings above M1 0.65 / M2 0.1 / M3 0.4), 0 errors, no poison messages. The API returns the same 72 through the gateway (`/api/findings`, `/api/stats/summary` high 10, detail, `/api/calibration`).
- Demo risks: the hosted Gemma answered 1 of 5 calls (2× 503, 2× timeout), then the breaker kept the rest rules-only; pre-warm or use the Ollama profile. Without the LLM, S3.4 stays `uncertain` and opens the M3 gate, so the Grant Thornton negative control is high-risk (0.78). The KDP news control has 17 low M1 findings (16 on "OKX" mentions matched to OKX Europe Markets, 1 on "Capital Markets").

### api
- `api-db-schema` applied and archived: Alembic `0001`-`0003` for `sources`, `documents`, `findings`, `job_errors`, `calibration_points`; one-shot `api-migrate` in the root stack.
- Merged with PR #15 (Kacper's review fixed in `api-db-schema-review-fixes`).
- `api-v1` applied and archived: REST under `/api` (all 11 contract paths), Socket.IO relay `iw:events` → `/events`, calibration curve from analyst labels, the `api` service in `api/compose.yaml`.
- In PR #21, stacked on PR #18 (`infra-compose`) and merging after it; Kacper's review fixed in `api-v1-review-fixes`.
- `api-rescan-state` (issue #71, M1 periodic update): `GET /findings/{id}` serves `document.scrape_meta.rescan` (`current`/`changed`/`removed`), derived from later documents of the same page and gone `job_errors`; no contract or table change. Open: a list badge needs an optional `Finding` field (contract change); `removed` from job errors needs the scraper to write `job_errors.url`.
- `POST /api/scans` runs a scan: the scraper consumes `iw:scan-requests` (#30). Verified in the #78 rehearsal: 17 requests through the gateway, all answered 202 and scanned.

### infra-compose
- Redis 8, object storage (MinIO, bucket `iw-raw`), the optional Ollama profile `llm`, project-scoped networks (`data`, `edge`, `egress`) and the smoke test `infra/tests/smoke.sh`: applied and archived, in PR #18.
- Kacper's two reviews of PR #18 fixed in `infra-compose-review-fixes` (archived).
- `OLLAMA_CONTEXT_LENGTH=8192` (default, override in `.env`) on the `ollama` service for the stage-2 LLM change: issue #32, branch `chore/ollama-context-length` (`infra-compose-review-fixes` follow-up 3).
- `ollama-pull` pulls `OLLAMA_MODELS` (default `gemma3:4b bge-m3`, `bge-m3` for `analytics-embeddings`, ADR 0313); `ollama` keeps both loaded (`OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_KEEP_ALIVE=30m`): issue #65, change `infra-ollama-bge-m3`, branch `infra/ollama-pull-bge-m3`.

## Active OpenSpec changes

- `findings-document-filter` (contract 1.1.0, `document_id` on `GET /findings`) archived in its own PR, linked to issue #33
- `api-v1` and `api-v1-review-fixes` archived in PR #21 (merges after PR #18)
- `api-db-schema` and `api-db-schema-review-fixes` archived in PR #15
- `infra-compose` and `infra-compose-review-fixes` archived in PR #18
- `analytics-worker` archived; `analytics-worker-review-fixes` (Kacper's PR #26 review) in PR #26
- `openspec-strict-format` archived in its own PR: 14 requirements across `database-schema`, `document-analysis`, `m2-compliance-rules`, `rest-api` and `shared-infrastructure` brought under OpenSpec 2.1.1's 500-character limit (text moved into scenarios, no behaviour change), so the CI job `Specs and hooks` passes. Its follow-ups name the fixes still due on `analytics-llm-p0` and `analytics-m1-m3`.
- `analytics-stored-content-hash` archived in its own PR (issue #31)

## Blockers and open decisions

- Contracts v1: the required core is frozen and accepted by Adam and Kacper ([ADR 0301](../decisions/0301-contracts-v1.md)). Optional fields, notably rendering metadata (`blocks`, screenshots), stay provisional until Integration #1 (Sat 17:00) and are still to be settled with Adam.
- Closed: the Alembic migration for the `documents` dedup index, `job_errors` and the published marker (`stream_published_at`) is Damian's ([ADR 0303](../decisions/0303-database-schema-ownership.md)) and is written: `api-db-schema`, PR #15.
