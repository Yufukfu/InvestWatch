---
when: Sat ~18:10
who: Damian
---

## What was done with AI

Kacper's Claude review of PR #15 (`api-db-schema`) raised 3 blocking, 3 major and 8 minor items; a side session checked each against the code, wrote `api-db-schema-review-fixes` and fixed them test-first with a scripted mutation check per group (20 mutations tried, 20 caught), then ran the root `docker compose up` on an empty volume under a throwaway project name

## Outcome / lesson

All blocking and major items were real. JSON `null` instead of SQL `NULL` passed every mapping test because reads mapped both to `None`; only an `IS NULL` query showed it. The new contract-enum test, reading `pg_constraint` instead of `tables.py`, found that `0001`'s CHECK names are doubled by the naming convention (follow-up). One mutant first survived because a scripted test edit had silently not applied: check the diff, not just the exit code. Redeclaring the data network without `name:` conflicts with `infra/compose.yaml` on `main`, so `api/compose.yaml` now declares none
