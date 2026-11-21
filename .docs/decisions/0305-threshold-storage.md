# 0305. Where module thresholds live and who emits `finding.high_risk`

- Status: proposed
- Date: 2026-11-21
- Deciders: C (proposal; A and B to review in PR #3)

## Context

Each module (M1, M2, M3) has a threshold that the calibration panel changes live (`GET/PUT /settings/thresholds` in [`contracts/openapi.yaml`](../../contracts/openapi.yaml)). The threshold turns the raw `score` into `risk_level` and decides when the dashboard gets a `finding.high_risk` alert ([integration-plan.md](../integration-plan.md) §4-§6, [`contracts/schemas/events.schema.json`](../../contracts/schemas/events.schema.json)).

Two existing statements pull in different directions: §6 of the integration plan lists `finding.high_risk` among the events published on `iw:events` (which analytics writes to), while [`analytics/CLAUDE.md`](../../analytics/CLAUDE.md) says the threshold is applied in `api`, never in analytics. The Socket.IO events the dashboard receives are the same in every option below; only the producer and the storage change.

## Options considered

1. **Thresholds in a Redis key (for example `iw:settings:thresholds`) written by the API; analytics reads it and emits `finding.high_risk`.** Fast reads, no extra table. Analytics then applies the threshold, contrary to `analytics/CLAUDE.md`, and the setting is lost if Redis is not persistent.
2. **Thresholds in a Postgres `settings` table; analytics reads it (cached) and emits `finding.high_risk`.** Durable and visible next to the findings. Same objection as option 1 about analytics applying the threshold; adds a table to the schema ([0303](0303-database-schema-ownership.md)).
3. **Thresholds stored by the API (Postgres or Redis); analytics publishes only `finding.created`; the API, when relaying events to Socket.IO, adds `risk_level` and emits `finding.high_risk` itself.** Keeps analytics threshold-free as `analytics/CLAUDE.md` requires; a threshold change takes effect immediately without touching analytics. The API relay becomes slightly smarter, and §6 of the integration plan would need a one-line update about who emits the event.

## Decision

Option 1: **thresholds in a Redis key (`iw:settings:thresholds`) written by the API; analytics reads it and emits `finding.high_risk`.**

Why (C):
- It keeps the event flow of [integration-plan.md](../integration-plan.md) §6, where analytics publishes `finding.high_risk` on `iw:events`; nothing in the flow changes.
- The API relay stays a plain pass-through from `iw:events` to Socket.IO with no threshold logic, which is less work before Integration #1.

## Consequences

- No extra table and fast reads; consistent with §6 of [integration-plan.md](../integration-plan.md), which lists `finding.high_risk` among the events analytics publishes on `iw:events`.
- Contradicts [`analytics/CLAUDE.md`](../../analytics/CLAUDE.md) ("the threshold is applied in `api`, never here"); that file must be changed if this ADR is accepted. `risk_level` is still derived by the API for REST responses ([0301](0301-contracts-v1.md)), so the threshold logic lives in two services and both must read the same key.
- A threshold change from the calibration panel affects only findings analysed after analytics re-reads the key; findings already published are not re-evaluated for `finding.high_risk`.
- Redis must be persistent (AOF or RDB in `docker compose`), otherwise thresholds are lost on restart; the API needs a default when the key is missing.
