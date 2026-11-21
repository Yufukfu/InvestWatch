# Architecture decision records

One file per decision: `NNNN-short-title.md`, copied from `0000-template.md`. Numbers come from the owner's range so parallel PRs never collide: Adam `01xx`, Kacper `02xx`, Damian `03xx`. ADRs are written by agents in the same PR as the change they record (or in an earlier docs-only PR that the implementing PR links), with the decision and a rationale that cites evidence; each is committed with `Status: accepted` and takes effect when the human approves and merges the PR; the Status column below shows it. Never auto-merge an ADR. An accepted ADR is not edited: a new ADR supersedes it and links the old one. Write one when a choice is hard to reverse or a teammate will ask "why".

Every ADR file must be listed in the table below (checked by `docs-check.mjs`).

| ADR | Decision | Status |
|---|---|---|
| [0101](0101-scraper-fetch-client.md) | Scraper fetch client | accepted (agent-written; effective on merge) |
| [0102](0102-scraper-job-queue.md) | Scraper job queue and scheduler | accepted (agent-written; effective on merge) |
| [0103](0103-first-social-platform.md) | First social platform | proposed (criteria only, no research; decided in `scraper-v2`) |
| [0104](0104-ingest-order-and-republish-sweep.md) | Ingest order, at-least-once delivery and the republish sweep | accepted (agent-written; effective on merge) |
| [0201](0201-web-stack-and-generated-client.md) | Dashboard stack: React + RTK Query client generated from the OpenAPI contract, MSW mocks | accepted; dev mocks superseded by [0206](0206-dashboard-data-from-backend.md) |
| [0202](0202-deployment-topology.md) | Per-module compose, Caddy HTTPS gateway, Postgres on an internal network | accepted |
| [0203](0203-dashboard-charts-recharts.md) | Dashboard charts: Recharts (the only chart library in `web/`) | accepted (takes effect when PR merges) |
| [0204](0204-frontend-architecture.md) | Frontend layering: feature data hooks wrap the generated client, components take props | accepted (takes effect when PR merges) |
| [0205](0205-status-per-domain.md) | Status split per domain: `.docs/STATUS.md` team-wide only, one file per owner in `.docs/status/` | accepted (takes effect when the PR merges) |
| [0206](0206-dashboard-data-from-backend.md) | Dashboard data from the backend only; MSW only in tests (supersedes 0201's dev mocks) | accepted (takes effect when PR merges) |
| [0207](0207-agent-push-and-pr.md) | Agents push their branch and open the PR; humans approve and merge | accepted (takes effect when the PR merges) |
| [0301](0301-contracts-v1.md) | Confirmation of data contracts v1 | accepted (takes effect when PR #3 merges) |
| [0302](0302-api-service.md) | Placement and stack of the REST/WebSocket API | accepted (takes effect when PR #3 merges) |
| [0303](0303-database-schema-ownership.md) | Ownership of the database schema and migrations (depends on [0302](0302-api-service.md)) | accepted (takes effect when PR #3 merges) |
| [0304](0304-llm-serving.md) | How Gemma is served to analytics | accepted (takes effect when PR #3 merges) |
| [0305](0305-threshold-storage.md) | Where module thresholds live and who emits `finding.high_risk` | accepted; default values superseded by [0316](0316-default-thresholds-from-evaluation.md) |
| [0306](0306-object-storage-image.md) | Object storage and Redis images: Chainguard MinIO build, Redis 8 from the ECR mirror | accepted (takes effect when the `infra-compose` PR merges) |
| [0307](0307-database-driver-and-table-layout.md) | Database driver (psycopg 3) and table layout (columns + JSONB, dedup and upsert keys) (depends on [0303](0303-database-schema-ownership.md)) | accepted (takes effect when the `api-db-schema` PR merges) |
| [0309](0309-llm-prompt-and-cache-contract.md) | LLM prompt, response and cache contract; the LLM decides only checks the rules defer (depends on [0304](0304-llm-serving.md)) | accepted (takes effect when the `analytics-llm-p0` PR merges) |
| [0310](0310-llm-chunking-and-budget.md) | LLM chunking on sentence boundaries, worst chunk wins, per-document budget below the claim idle time (depends on [0304](0304-llm-serving.md)) | accepted (takes effect when the `analytics-llm-p0` PR merges) |
| [0308](0308-m3-s34-gate.md) | M3 gate: a recommendation of instruments alone lifts the 0.4 cap ("may indicate" advice, personalisation unconfirmed) | accepted (takes effect when PR #35 merges) |
| [0311](0311-knf-registry-source-and-ids.md) | KNF registry: HTML lists parsed by a manual loader, committed `registry/knf.csv`, uuid5 firm ids | accepted (takes effect when the `analytics-knf-registry` PR merges) |
| [0312](0312-gold-set-evaluation.md) | Gold-set evaluation feeds the calibration panel: fictional eval registry, strict/review readings, idempotent default-stack run, labels plus gold in the API | accepted (takes effect when the `analytics-eval-calibration` PR merges) |
| [0316](0316-default-thresholds-from-evaluation.md) | Default thresholds from the gold-set evaluation (best F1 per module, rules-only; supersedes 0305's default values only) | accepted (takes effect when the `analytics-eval-calibration` PR merges) |

## Candidate topics (evidence only, rationale to be decided by a human)

- **Playwright boundary:** which sources must be rendered, because `blocks` and screenshots (`.docs/integration-plan.md` §3) feed rules R4-R8 and R13 (`.docs/analytics-plan.md` §5). Owner Adam, with Damian.
- **First social platform** (team decision: one platform first). Owner Adam.
