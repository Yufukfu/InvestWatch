## Context

Contracts v1 are frozen (ADR 0301; the provisional window closed at Integration #1, Sat 17:00), so this is the first post-freeze change: it needs the whole team's OK, a version bump and `IW_CONTRACT_CHANGE=1` on the commits that touch `contracts/openapi.yaml` and `contracts/mocks/`. The change touches two services Damian owns (`api/`, `contracts/mock-server`) and one consumer Kacper owns (`web/`, not edited here).

Today `GET /api/findings` (api `routes/findings.py`, mock `iw_mock_server/app.py`) builds a list of AND conditions from optional query parameters; `source_id` is already matched through the document. The `findings` table has the unique constraint `uq_findings_document_module (document_id, module)`, whose index leads with `document_id`.

## Goals / Non-Goals

**Goals:**
- The dashboard can fetch every finding of one document in one call, independent of the list's current page and sort.
- The mock server and its mocks show the case (one post, M1 + M3).
- No behaviour change for a request without `document_id`.

**Non-Goals:**
- A new route (`GET /documents/{id}/findings`), a `documents` list endpoint, or embedding sibling findings in `GET /findings/{id}`.
- Any change in `web/`, in analytics, or in the database schema.

## Decisions

1. **A query parameter on `GET /findings`, not a new route.** Kacper asked for exactly this; it reuses the list shape his code already maps (`items`, `total`, `page`, `page_size`), and combines with `module=` and pagination for free. Alternative: embed `related_findings` in `GET /findings/{id}`: a response-shape change (schema edit) and a second query in the detail route, so a larger contract change for the same need.
2. **Type `string`, `format: uuid`, validated as a UUID.** Matches `source_id`; FastAPI's `UUID` type gives a 422 naming the parameter for a malformed value, so a typo never silently returns an empty list, and no text reaches SQL unparsed. An unknown but well-formed id is a valid empty result (200, `total` 0), like every other filter.
3. **Version 1.1.0 (minor).** The change is additive and optional, so a semver minor bump: clients built against 1.0.0 keep working. The api and mock server report the same version in their FastAPI apps so `/openapi.json` of each service matches the contract file. The bump is recorded in `contracts/README.md`; no ADR, because nothing here is hard to reverse (ADR 0301 already states the post-freeze rule this follows).
4. **Mock data: a new scenario with a `findings` list, existing ids unchanged.** `generate_mocks.py` keeps `finding=` for the nine existing scenarios (their ids stay `uid("finding-" + key)`) and accepts `findings=[...]` for the new one, whose ids are `uid(f"finding-{key}-{module}")`. The new post is placed 4 hours back so `findings[0]` (source of `finding-detail.json`) and `findings[:3]` (source of `events.json`) stay the same; the M3 finding is detected 20 seconds after the M1 one, as the LLM step runs later, which also keeps the sort deterministic. Alternative: add an M3 finding to an existing M1 post (`m1-ig-jan`): its text has no investment advice, so the M3 finding would be implausible in the demo.

## Risks / Trade-offs

- [Kacper's snapshot `web/src/api/openapi.json` and `web/src/test/fixtures/` lag behind 1.1.0] → he re-syncs with `npm run api:generate` in his `web/` PR; his tests derive counts from the fixtures, so they keep passing until then.
- [Mock counts change (9 → 11 findings, 9 → 10 documents)] → the mock-server tests that pin counts are updated in the same commit; `summary.json`, `trend.json` and `sources.json` are regenerated, never hand-edited.
- [Team does not agree] → nothing in `contracts/` is committed until Damian confirms Adam's and Kacper's OK; the api part alone would not be served (the api serves the contract exactly), so the change waits as a whole.

## Migration Plan

No migration. Deploy is the normal compose rebuild of `api` and `mock-api`. Rollback: revert the PR; clients that never send `document_id` are unaffected either way.
