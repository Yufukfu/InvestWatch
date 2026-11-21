# api (module C)

Thin FastAPI REST layer plus Socket.IO gateway over the same database the scraper and analytics write to. The contract lives in the docs, not here:

- Architecture: [`doc/integration-plan.md`](../doc/integration-plan.md) §1. REST routes: §5. Real-time events (Socket.IO namespace `/events`): §6. Shared conventions: §7.
- `Finding` shape and how `risk_level` is derived from the module threshold: §4.

## Rules that are easy to get wrong

- Database migrations (Alembic) live here and nowhere else; no service creates tables by hand.
- `risk_level` is computed by the API from the current threshold. Changing a threshold recomputes it; the stored `score` is never rewritten.
- Subscribe to Redis Pub/Sub `iw:events` and fan out to Socket.IO; do not poll the database for new findings.
- Every service exposes `/health`. Config is env-only (`DATABASE_URL`, `REDIS_URL`, `MINIO_*`).
- User-facing summaries are Polish; code, logs and docs are English; logs are JSON on stdout.

## Stack and done

Python (FastAPI). Done means each route in §5 matches the contract, a status change emits `finding.updated`, and the dashboard works against it without code changes from its mock data.
