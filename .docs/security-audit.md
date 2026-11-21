# Dependency audits

Dependency and secret scan results before a merge to `main` ([integration-plan.md](integration-plan.md) §7). How to run each scan: [supply-chain.md](supply-chain.md) ([ADR 0209](decisions/0209-supply-chain-scanning.md)). Newest first; one row per run.

| Date | Module | Command | Result |
|---|---|---|---|
| 2026-11-21 | repository (`chore/supply-chain-adr`, ADR 0209) | `gitleaks git` over `origin/main` (Gitleaks v8.28.0, image digest `sha256:cdbb7c95…`, `--redact`; commit count not re-recorded: the earlier 276 was not reproduced, `origin/main` is 390 commits at bb770a0; rerun on a named SHA pending) | 2 findings, both false positives: rule `generic-api-key` on mock record ids (`key="m2-…"`) in `contracts/mocks/generate_mocks.py` lines 145 and 299. Not rerun in the review round of 2026-11-21. No secret in history; allowlist entry due with the CI follow-up |
| 2026-11-21 | web (`chore/supply-chain-adr`) | `npm audit --audit-level=high` in `web/` (npm 10.9.2) | found 0 vulnerabilities |
| 2026-11-21 | analytics (`analytics-worker-review-fixes`) | `pip-audit -r analytics/requirements.txt -r analytics/requirements-dev.txt` (pip-audit 2.10.1; psycopg[binary] 3.3.9, redis 8.1.0, fakeredis 2.40.0) | No known vulnerabilities found |
| 2026-11-21 | api (`api-v1`) | `pip-audit -r api/requirements.txt -r api/requirements-dev.txt` (pip-audit 2.10.1; FastAPI 0.165.0, python-socketio 5.18.1, redis 8.1.0, minio 7.2.20) | No known vulnerabilities found |
| 2026-11-21 | api (`api-db-schema`) | `pip-audit -r api/requirements.txt -r api/requirements-dev.txt` (pip-audit 2.10.1) | No known vulnerabilities found |

## Service notes

### analytics worker (`analytics/compose.yaml`, PR #26)

- **Credentials held:** `DATABASE_URL` as the app role `iw_app` (CRUD, no DDL; it reads `documents` and writes `findings`), and `REDIS_URL` with the Redis password (it reads `iw:documents`, publishes `iw:events`, reads `iw:settings:thresholds`). Both come from the root `.env`. Neither appears in logs: store errors keep only the class and SQLSTATE or the first libpq line, and a malformed `DATABASE_URL` is reported without quoting it.
- **Networks:** infra's internal `data` network only; no host port, no `edge`, no `egress` (no outbound call until the LLM client lands with `analytics-llm-p0`).
- **`/health`:** unauthenticated `GET /health` on `0.0.0.0:8001` inside the container, reachable only from other containers on `data`; not published to the host and not routed through the gateway. It returns only `{status, redis, db}` booleans, uses a short-lived DB connection per check and a 2 s socket timeout.
- **Untrusted input:** stream entries and scraped rows are untrusted. Undecodable bytes become an acknowledged `invalid_message`. A row bigger than `MAX_DOCUMENT_BYTES` (default 2 MB, measured in SQL before loading) is acknowledged as `invalid_document`, so a huge page cannot OOM-kill the container in a loop. All SQL is parameterised. Residual: one huge stream field (Redis allows 512 MB) is read before any check; only Redis password holders can write one.
- **Container:** non-root (uid 10001), read-only root filesystem, `cap_drop: [ALL]`, `no-new-privileges`, CPU and memory limits, base image pinned by digest.
