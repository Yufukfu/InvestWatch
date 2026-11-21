# Architecture Decision Records

Every architecture decision is recorded here before it is implemented. An ADR is short: context, decision, consequences. Code that depends on an open decision waits for its ADR.

## Process

1. Copy [`template.md`](template.md) to `NNNN-short-title.md` with the next number.
2. Status `Proposed`, open a pull request, ask the people affected (see "Deciders").
3. After agreement: status `Accepted`. A later change gets a new ADR that supersedes the old one.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-repository-structure.md) | Repository structure: `scraper`, `analytics`, `web` | Accepted |

## Backlog (to decide)

Topics only. Nothing below is decided. The drafts in `doc/integration-plan.md` are input, not decisions.

| Topic | Decides | Affects | Notes |
|---|---|---|---|
| Data contracts between services (`ScrapedDocument`, `Finding`) | C | A, B | plan draft, sections 3–4 |
| Integration mechanism scraper → analytics (stream, queue, DB polling) | C, A | A, C | |
| Scraper design: collectors, job queue, scheduler, static vs rendered pages, first social platform | A | C | |
| Storage: database schema and migration ownership, object storage | C | A | official `minio/minio` and `quay.io/minio/minio` images cannot be pulled; `chainguard/minio` can (checked with Docker on 21.11) |
| REST API and real-time events: where the API service lives, endpoints, WebSocket events | C | B | plan lists a separate `api` folder, not in ADR-0001 |
| LLM provider and runtime | C | all | task requires on-prem open-source models; a free cloud API only for development |
| Dashboard stack: framework, UI library, charts | B | – | |
| Deployment: docker compose layout, configuration, Quick Start | C | all | |
