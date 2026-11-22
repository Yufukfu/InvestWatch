---
when: Sun 03:22
who: Damian
---

## What was done with AI

A Claude Code session, started from the issue triage session, built the API side of issue #115 as contract 1.3.0: `POST /findings/bulk-status`, `GET /findings/export` (CSV of the filtered list) and `m2_coverage` in `/stats/summary`, in `api/` and the mock server. The export reuses the list's filters through one FastAPI dependency, and the bulk route reuses the PATCH update. Tests first, then a mutation check

## Outcome / lesson

Branch `api/bulk-export-coverage`. Two mutants survived the first tests. Every mock M2 finding has a registry id, so the mock coverage test could not tell "matched" from "has a firm" until a test edited the mock data. The CSV formula guard's tab and CR cases had no test. PDF export was skipped because it was not trivial
