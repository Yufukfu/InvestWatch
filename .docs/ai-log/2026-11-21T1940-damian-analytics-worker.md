---
when: Sat ~19:40
who: Damian
---

## What was done with AI

Had a Claude Code side session propose and apply `analytics-worker` (the stream worker, Postgres store, `iw:events` publisher, `/health`, container) while a coordinating session relayed decisions from the parallel `api-db-schema` and `infra-compose` sessions. Per task group: failing test first, a scripted mutate-and-restore check, and a fresh-agent review (`iw-reviewer` brief) on the pinned range.

## Outcome / lesson

Branch `analytics/analytics-worker`, stacked on PR #18. Reviews caught what the tests missed: the `/health` server leaked one Postgres connection per request (would have used up `max_connections` in ~17 min), a malformed `DATABASE_URL` echoed the password from libpq, a `no cache` test counted reads in the wrong place, and the in-memory upsert diverged from the API's replaced-field list. A full-stack run showed SIGKILL on `docker compose stop` (Docker Desktop's 1 s stop timeout), fixed by leaving the idle read on SIGTERM. Lesson: a generated `.env` sets `COMPOSE_PROJECT_NAME`, so sourcing it silently retargets compose commands to another project; pass `-p` explicitly.
