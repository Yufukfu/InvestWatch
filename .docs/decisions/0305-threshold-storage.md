# 0305. Where module thresholds live and who emits `finding.high_risk`

- Status: proposed
- Date: 2026-11-21
- Deciders: A, B, C (to be confirmed)

## Context

Each module (M1, M2, M3) has a threshold that the calibration panel changes live (`GET/PUT /settings/thresholds` in [`contracts/openapi.yaml`](../../contracts/openapi.yaml)). The threshold turns the raw `score` into `risk_level` and decides when the dashboard gets a `finding.high_risk` alert ([integration-plan.md](../integration-plan.md) §4-§6, [`contracts/schemas/events.schema.json`](../../contracts/schemas/events.schema.json)).

Two existing statements pull in different directions: §6 of the integration plan lists `finding.high_risk` among the events published on `iw:events` (which analytics writes to), while [`analytics/CLAUDE.md`](../../analytics/CLAUDE.md) says the threshold is applied in `api`, never in analytics. The Socket.IO events the dashboard receives are the same in every option below; only the producer and the storage change.

## Options considered

1. **Thresholds in a Redis key (for example `iw:settings:thresholds`) written by the API; analytics reads it and emits `finding.high_risk`.** Fast reads, no extra table. Analytics then applies the threshold, contrary to `analytics/CLAUDE.md`, and the setting is lost if Redis is not persistent.
2. **Thresholds in a Postgres `settings` table; analytics reads it (cached) and emits `finding.high_risk`.** Durable and visible next to the findings. Same objection as option 1 about analytics applying the threshold; adds a table to the schema ([0303](0303-database-schema-ownership.md)).
3. **Thresholds stored by the API (Postgres or Redis); analytics publishes only `finding.created`; the API, when relaying events to Socket.IO, adds `risk_level` and emits `finding.high_risk` itself.** Keeps analytics threshold-free as `analytics/CLAUDE.md` requires; a threshold change takes effect immediately without touching analytics. The API relay becomes slightly smarter, and §6 of the integration plan would need a one-line update about who emits the event.

## Decision

_To be written by the team (A, B, C)._

## Consequences

_To be written together with the decision._
