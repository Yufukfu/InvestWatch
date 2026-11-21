# Architecture decision records

One file per decision: `NNNN-short-title.md`, copied from `0000-template.md`. Numbers come from the owner's range so parallel PRs never collide: A `01xx`, B `02xx`, C `03xx`. ADRs are written by agents in the same PR as the change they record, with the decision and a rationale that cites evidence; each is committed with `Status: accepted` and takes effect when the human approves and merges the PR; the Status column below shows it. Never auto-merge an ADR. An accepted ADR is not edited: a new ADR supersedes it and links the old one. Write one when a choice is hard to reverse or a teammate will ask "why".

Every ADR file must be listed in the table below (checked by `docs-check.mjs`).

| ADR | Decision | Status |
|---|---|---|
| [0101](0101-scraper-fetch-client.md) | Scraper fetch client | proposed (agent draft, no decision) |
| [0102](0102-scraper-job-queue.md) | Scraper job queue and scheduler | proposed (agent draft, no decision) |
| [0103](0103-first-social-platform.md) | First social platform | proposed (criteria only, no research) |
| [0201](0201-web-stack-and-generated-client.md) | Dashboard stack: React + RTK Query client generated from the OpenAPI contract, MSW mocks | accepted |
| [0202](0202-deployment-topology.md) | Per-module compose, Caddy HTTPS gateway, Postgres on an internal network | accepted |

## Candidate topics (evidence only, rationale to be decided by a human)

- **Scraper fetch client:** `noble-tls` (v0.1.9 on PyPI at time of writing) vs `curl_cffi` vs plain `httpx`. Read the installed package's real API first. Owner A.
- **Playwright boundary:** which sources must be rendered, because `blocks` and screenshots (`.docs/integration-plan.md` §3) feed rules R4-R8 and R13 (`.docs/analytics-plan.md` §5). Owner A, with C.
- **Job queue and scheduler** for the scraper: open source, undecided. Owner A.
- **First social platform** (team decision: one platform first). Owner A.
- **Contract v1 confirmation** by A and B (open in the team sync notes, `.docs/integration-plan.md`). Owner C.
