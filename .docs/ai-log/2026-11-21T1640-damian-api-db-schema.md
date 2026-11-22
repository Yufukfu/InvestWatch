---
when: Sat ~16:40
who: Damian
---

## What was done with AI

Claude Code proposed `api-db-schema` and `api-v1`, then applied `api-db-schema` from a coordinating session: Alembic revisions for the shared tables, test-first against a throwaway Postgres 17, a mutate-and-restore check per task group (46 mutations tried) and a fresh reviewer agent per group

## Outcome / lesson

Branch `api/api-v1`. Reviews caught what the author missed: credentials could reach logs through exception text, the test fixture could create roles on a non-local server, and a bare `ON CONFLICT DO NOTHING` would hide a reused document id; all fixed test-first. A sibling session also had an ADR 0306, renumbered to 0307 (claim numbers in the shared notes before writing). Docker Desktop failed to start at first, which blocked every DB test until Damian fixed it
