# 0301. Confirmation of data contracts v1

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written from Damian's choices; accepted by: pending approval of PR #3

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

Option 3: **accept a minimal core now, extend later**, applied to every v1 contract file:

- **Frozen core (since Sat 14:30):** the `required` lists of every schema: `ScrapedDocument` (`id, platform, source_kind, url, fetched_at, text`, and `viewport, text, font_size_px, visible` inside a block), `Finding` (its 11 required fields and `rule_id, name, result, severity` inside a rule result), `Source` (`id, name, platform, url, source_kind, target_modules, active`), and the required fields of the envelopes in `events.schema.json` (`document_message`, `scan_request`, `finding_brief`, `event`). In `openapi.yaml`: the 11 paths with their methods and the required fields of their responses, which is what Kacper builds the dashboard against.
- **Provisional until Integration #1 (Sat 17:00):** every non-required property (for example `blocks`, `screenshots`) and every optional query parameter. After Integration #1 the whole of v1 is frozen and the general rule applies.

How this fits the freeze hook: `git-guard` freezes the whole files under `contracts/schemas/`, `contracts/mocks/` and `contracts/openapi.yaml` and cannot tell fields apart, so the hook stays as it is. A change to a provisional field before Sat 17:00 is committed with the escape `IW_CONTRACT_CHANGE=1`, without a version bump, in a PR reviewed by the consumers of that field (Adam for documents and sources, Kacper for the REST API), with regenerated mocks and `python contracts/validate.py` passing. A change to the frozen core, or any change after Sat 17:00, still needs the whole team and a version bump. Root `CLAUDE.md` and `contracts/CLAUDE.md` state this exception.

Why (Damian): the remaining fields, `blocks` and `screenshots` in particular, depend on decisions that are still open on Adam's side (Playwright boundary, fetch client), so freezing them now would freeze guesses.

## Consequences

- Everyone builds against the frozen core today; it changes only with the whole team and a version bump.
- Provisional fields are where mismatches between services are most likely: any producer or consumer of an optional field checks it against `contracts/validate.py` and the mocks before Integration #1.
- Each provisional change uses `IW_CONTRACT_CHANGE=1`, so per root `CLAUDE.md` the human is told every time the flag is used; review by the field's consumers replaces the version bump for this window only.
- Rules R4-R8 and R13 keep returning `not_applicable` until `blocks`/`screenshots` are settled ([analytics-plan.md](../analytics-plan.md) §5).
- At Integration #1 (Sat 17:00) the provisional window closes; fields nobody produces stay optional and are documented as unused rather than removed, so no version bump is needed.
