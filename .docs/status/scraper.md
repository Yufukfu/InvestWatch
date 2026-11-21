# Status: scraper (Adam)

Edit only this file for `scraper/` state. Last updated: 2026-11-21 (Sat).

## State

- SDLC merged.
- `scraper-ingest` implemented against Damian's `0001_initial` (document build, validation, dedup insert, MinIO, `iw:documents` after commit, republish sweep, `job_errors` sink), in review.
- `scraper-v1` and `scraper-orchestration` in progress.
- ADRs 0101, 0102 and 0104 accepted with this change, 0103 criteria only.

## Active OpenSpec changes

- `scraper-ingest` (in review), `scraper-v1`, `scraper-orchestration`

## Blockers and open decisions

- Scraper fetch client and job queue are decided in ADRs 0101 and 0102 (agent-written, effective when the `scraper-ingest` PR merges). The first social platform is open: ADR 0103 has criteria only, no research yet.
- Open with Damian before `scraper-v1` can be applied: the `scrape_meta.scraper` value for a TLS-impersonating client (v1 enum is `playwright|httpx|api|manual`). The Alembic migration is settled: Damian's `0001_initial` in `api/migrations/` has the `documents` unique index, `job_errors` and `stream_published_at`; `redis`, `minio` and `minio-init` come with Damian's `infra-compose`.
- Playwright is required for sources that must provide `blocks`/`screenshots` (rules R4-R8, R13).
- Social media: one platform first; which one is open (ADR 0103).
