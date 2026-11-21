# 0001. Repository structure: `scraper`, `analytics`, `web`

- **Status:** Accepted
- **Date:** 2026-11-21
- **Deciders:** B (owner of the repository structure, per the team sync)

## Context

The task requires a modular architecture of lightweight services, with frontend, backend and AI separated into independent, readable modules, and no heavy monorepo structures. The team has three people, each owning one area: A (scraper), B (dashboard), C (analytics).

## Decision

One repository with three top-level service folders, one per owner:

| Folder | Purpose | Owner |
|---|---|---|
| `scraper/` | data collection | A |
| `analytics/` | analytics modules M1–M3, LLM | C |
| `web/` | dashboard | B |

`doc/` holds shared documentation: UKNF materials, plans, ADRs, AI work log.

Each service folder is self-contained: its own dependencies, `.gitignore`, `README.md` and, later, its own container image. No shared code packages between folders; services communicate only through agreed contracts.

## Consequences

- Clear ownership: each person works in one folder, so conflicts between branches stay rare.
- Cross-service interfaces must be agreed explicitly, because code cannot be shared. Each contract gets its own ADR (see the backlog).
- The draft integration plan lists separate `api` and `contracts` folders. Their placement is an open question in the backlog and needs a decision before implementation.
