# Architecture decision records

One file per decision: `NNNN-short-title.md`, copied from `0000-template.md`. Numbers come from the owner's range so parallel PRs never collide: A `01xx`, B `02xx`, C `03xx`. ADRs are written by a human; agents may draft Context, Options and evidence, never the decision or its rationale. Never auto-merge an ADR. An accepted ADR is not edited: a new ADR supersedes it and links the old one. Write one when a choice is hard to reverse or a teammate will ask "why".

Every ADR file must be listed in the table below (checked by `docs-check.mjs`).

| ADR | Decision | Status |
|---|---|---|
| [0301](0301-contracts-v1.md) | Confirmation of data contracts v1 | proposed |
| [0302](0302-api-service.md) | Placement and stack of the REST/WebSocket API | proposed |
| [0303](0303-database-schema-ownership.md) | Ownership of the database schema and migrations | proposed |
| [0304](0304-llm-serving.md) | How Gemma is served to analytics | proposed |
| [0305](0305-threshold-storage.md) | Where module thresholds live and who emits `finding.high_risk` | proposed |

## Candidate topics (evidence only, rationale to be decided by a human)

- **Scraper fetch client:** `noble-tls` (v0.1.9 on PyPI at time of writing) vs `curl_cffi` vs plain `httpx`. Read the installed package's real API first. Owner A.
- **Playwright boundary:** which sources must be rendered, because `blocks` and screenshots (`.docs/integration-plan.md` §3) feed rules R4-R8 and R13 (`.docs/analytics-plan.md` §5). Owner A, with C.
- **Job queue and scheduler** for the scraper: open source, undecided. Owner A.
- **First social platform** (team decision: one platform first). Owner A.
