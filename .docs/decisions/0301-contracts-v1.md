# 0301. Confirmation of data contracts v1

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written from Damian's choices; accepted by Adam, Kacper and Damian via PR #3

## Context

The scraper (Adam), analytics (Damian), API (Damian) and dashboard (Kacper) exchange data through the contracts in [`contracts/`](../../contracts/README.md): `ScrapedDocument`, `Finding`, `Source`, stream messages and events, plus the REST API in `contracts/openapi.yaml`. They are described in [integration-plan.md](../integration-plan.md) §3-§6 and are a **draft v1** proposed by Damian. The root `CLAUDE.md` says contracts are frozen after Sat 14:30 and a change needs the whole team and a version bump, but Adam and Kacper have not confirmed v1 yet, so the freeze has nothing confirmed to freeze.

Open points known today:

- `blocks` and `screenshots` in `ScrapedDocument` (rendered text metadata from Playwright). Rules R4-R8 and R13 ([analytics-plan.md](../analytics-plan.md) §5) need them; without them those rules return `not_applicable`. Effort sits with Adam (Playwright boundary is a separate candidate ADR, owner Adam).
- Who emits `finding.high_risk` and where thresholds live: see [0305](0305-threshold-storage.md).
- Naming: the integration plan says `dashboard`, Kacper's layout uses `web/`. No field in the contracts depends on it.
- `risk_level` is derived by the API from `score` and the threshold; analytics stores only the raw `score` ([`analytics/CLAUDE.md`](../../analytics/CLAUDE.md)).

Evidence: `python contracts/validate.py` validates all mocks against the schemas (9 documents, 9 findings, 4 sources, 9 events) and rejects a deliberately broken finding.

## Options considered

1. **Accept v1 as it is.** Everyone builds against the current schemas and mocks now; Kacper already has mocks for every endpoint. Open points are resolved by their own ADRs without touching the schemas (`blocks` is optional, `high_risk` is an event the dashboard receives either way).
2. **Accept v1 with named amendments first.** The team lists changes (for example making `blocks` required for `platform = web`, or dropping fields nobody produces) and Damian applies them before anyone codes against v1. Costs a short round of edits and a re-validation; avoids an early v2.
3. **Accept a minimal core now, extend later.** Freeze only the required fields (`ScrapedDocument`: `id, platform, source_kind, url, fetched_at, text`; `Finding`: the required list in the schema) and treat everything else as provisional until Integration #1. Most flexible, but "provisional" fields are exactly where mismatches between services appear.

## Decision

Option 3: **accept a minimal core now, extend later.** Frozen at Sat 14:30 are only the required fields: `ScrapedDocument` (`id, platform, source_kind, url, fetched_at, text`) and the required list of `Finding` in `contracts/schemas/finding.schema.json`. Every other field stays provisional until Integration #1.

Why (Damian): the remaining fields, `blocks` and `screenshots` in particular, depend on decisions that are still open on Adam's side (Playwright boundary, fetch client), so freezing them now would freeze guesses.

## Consequences

- Everyone can build against the required fields today; changing them after the freeze needs the whole team and a version bump (root `CLAUDE.md`).
- Provisional fields are where mismatches between services are most likely: producers and consumers of any optional field must check it against `contracts/validate.py` and the mocks before Integration #1.
- Rules R4-R8 and R13 keep returning `not_applicable` until `blocks`/`screenshots` are settled ([analytics-plan.md](../analytics-plan.md) §5).
- Revisit at Integration #1 (Sat 17:00): promote the provisional fields that are actually produced to frozen, drop the rest, and record it in a superseding ADR.
