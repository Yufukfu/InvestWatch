# Architecture decision records

One file per decision: `NNNN-short-title.md`, copied from `0000-template.md`. Numbers come from the owner's range so parallel PRs never collide: A `01xx`, B `02xx`, C `03xx`. ADRs are written by agents in the same PR as the change they record, with the decision and a rationale that cites evidence; each is committed with `Status: accepted` and takes effect when the human approves and merges the PR; the Status column below shows it. Never auto-merge an ADR. An accepted ADR is not edited: a new ADR supersedes it and links the old one. Write one when a choice is hard to reverse or a teammate will ask "why".

Every ADR file must be listed in the table below (checked by `docs-check.mjs`).

| ADR | Decision | Status |
|---|---|---|
| [0101](0101-scraper-fetch-client.md) | Scraper fetch client | accepted (agent-written; effective on merge) |
| [0102](0102-scraper-job-queue.md) | Scraper job queue and scheduler | accepted (agent-written; effective on merge) |
| [0103](0103-first-social-platform.md) | First social platform | proposed (criteria only, no research; decided in `scraper-v2`) |
| [0104](0104-ingest-order-and-republish-sweep.md) | Ingest order, at-least-once delivery and the republish sweep | accepted (agent-written; effective on merge) |
| [0301](0301-contracts-v1.md) | Confirmation of data contracts v1 | accepted (takes effect when PR #3 merges) |
| [0302](0302-api-service.md) | Placement and stack of the REST/WebSocket API | accepted (takes effect when PR #3 merges) |
| [0303](0303-database-schema-ownership.md) | Ownership of the database schema and migrations (depends on [0302](0302-api-service.md)) | accepted (takes effect when PR #3 merges) |
| [0304](0304-llm-serving.md) | How Gemma is served to analytics | accepted (takes effect when PR #3 merges) |
| [0305](0305-threshold-storage.md) | Where module thresholds live and who emits `finding.high_risk` | accepted (takes effect when PR #3 merges) |

## Candidate topics (evidence only, rationale to be decided by a human)

- **Playwright boundary:** which sources must be rendered, because `blocks` and screenshots (`.docs/integration-plan.md` §3) feed rules R4-R8 and R13 (`.docs/analytics-plan.md` §5). Owner A, with C.
- **First social platform** (team decision: one platform first). Owner A.
