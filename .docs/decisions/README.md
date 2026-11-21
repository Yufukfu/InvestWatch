# Architecture decision records

One file per decision: `NNNN-short-title.md`, copied from `0000-template.md`. Numbers come from the owner's range so parallel PRs never collide: A `01xx`, Kacper `02xx`, Damian `03xx`. ADRs are written by agents in the same PR as the change they record (or in an earlier docs-only PR that the implementing PR links), with the decision and a rationale that cites evidence; each is committed with `Status: accepted` and takes effect when the human approves and merges the PR; the Status column below shows it. Never auto-merge an ADR. An accepted ADR is not edited: a new ADR supersedes it and links the old one. Write one when a choice is hard to reverse or a teammate will ask "why".

Every ADR file must be listed in the table below (checked by `docs-check.mjs`).

| ADR | Decision | Status |
|---|---|---|
| [0101](0101-scraper-fetch-client.md) | Scraper fetch client | proposed (agent draft, no decision) |
| [0102](0102-scraper-job-queue.md) | Scraper job queue and scheduler | proposed (agent draft, no decision) |
| [0103](0103-first-social-platform.md) | First social platform | proposed (criteria only, no research) |
| [0201](0201-web-stack-and-generated-client.md) | Dashboard stack: React + RTK Query client generated from the OpenAPI contract, MSW mocks | accepted; dev mocks superseded by [0205](0205-dashboard-data-from-backend.md) |
| [0202](0202-deployment-topology.md) | Per-module compose, Caddy HTTPS gateway, Postgres on an internal network | accepted |
| [0203](0203-dashboard-charts-recharts.md) | Dashboard charts: Recharts (the only chart library in `web/`) | accepted (takes effect when PR merges) |
| [0204](0204-frontend-architecture.md) | Frontend layering: feature data hooks wrap the generated client, components take props | accepted (takes effect when PR merges) |
| [0205](0205-dashboard-data-from-backend.md) | Dashboard data from the backend only; MSW only in tests (supersedes 0201's dev mocks) | accepted (takes effect when PR merges) |
| [0301](0301-contracts-v1.md) | Confirmation of data contracts v1 | accepted (takes effect when PR #3 merges) |
| [0302](0302-api-service.md) | Placement and stack of the REST/WebSocket API | accepted (takes effect when PR #3 merges) |
| [0303](0303-database-schema-ownership.md) | Ownership of the database schema and migrations (depends on [0302](0302-api-service.md)) | accepted (takes effect when PR #3 merges) |
| [0304](0304-llm-serving.md) | How Gemma is served to analytics | accepted (takes effect when PR #3 merges) |
| [0305](0305-threshold-storage.md) | Where module thresholds live and who emits `finding.high_risk` | accepted (takes effect when PR #3 merges) |
| [0307](0307-database-driver-and-table-layout.md) | Database driver (psycopg 3) and table layout (columns + JSONB, dedup and upsert keys) (depends on [0303](0303-database-schema-ownership.md)) | accepted (takes effect when the `api-db-schema` PR merges) |

## Candidate topics (evidence only, rationale to be decided by a human)

- **Scraper fetch client:** `noble-tls` (v0.1.9 on PyPI at time of writing) vs `curl_cffi` vs plain `httpx`. Read the installed package's real API first. Owner Adam.
- **Playwright boundary:** which sources must be rendered, because `blocks` and screenshots (`.docs/integration-plan.md` §3) feed rules R4-R8 and R13 (`.docs/analytics-plan.md` §5). Owner Adam, with Damian.
- **Job queue and scheduler** for the scraper: open source, undecided. Owner Adam.
- **First social platform** (team decision: one platform first). Owner Adam.
