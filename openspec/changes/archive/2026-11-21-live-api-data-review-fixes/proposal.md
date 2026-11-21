# Proposal

## Why

Adam's review of PR #25 (`live-api-data`) asked for changes: stale mock wording left in the specs (rule: no "to follow"), a guard test with two bypasses, and no plain statement of what the compose demo looks like without a REST backend. The change `live-api-data` is already archived, so the fixes go in this follow-up change in the same PR.

## What Changes

- Guard test (`web/src/noBrowserMocks.test.ts`): shipped code (sources outside `src/test/`, `public/`, root `*.html`/`*.js`/`*.mjs`/`*.cjs`, `.env*`, `vite-env.d.ts`) must not import from `src/test/`, and none of it may mention `useMocks` or `VITE_USE_MOCKS`; no file under `src/` may use `msw/browser` or `setupWorker`. Both bypasses from the review were reproduced in a scratch copy first and now fail the test.
- Test network default handler answers `bucket=day` with an error, so a test that forgets `server.use` fails loudly.
- Specs: the `web-foundation` delta says Vitest network fake and covers all shipped files. Two edits are made by hand in `openspec/specs/`, because a MODIFIED block cannot rename a scenario and the Purpose is not a requirement: the Purpose of `web-foundation` (no longer "mock mode") and the two `web-trend` scenario titles ("Chart from the backend", "Day data from the backend"); no behaviour changes.
- Docs: ADR 0206 and `.docs/status/dashboard.md` / `.docs/STATUS.md` state the demo consequence and plan; `web/README.md` documents running the mock server container.

**Decision (Kacper, this review):** we do not wait for `api-v1` (PR #21) and do not add a REST backend to `compose.yaml` now. The dashboard works against Damian's mock server (`contracts/mock-server`), which Kacper runs as a separate Docker container, until there is sensible data. Nothing changes on the backend. Before the demo and the hand-in, `docker compose up` will run the whole system.

**Out of scope:** `sync-contracts.mjs` write-path tests (as before this PR); the `api-v1` rollback wording in Damian's change (see `follow-ups.md`). Owner Kacper.

## Capabilities

### Modified Capabilities
- `web-foundation`: the "no fake backend" check covers all shipped files and `src/test/` imports; wording says Vitest network fake.

## Impact

- Code: `web/src/noBrowserMocks.test.ts`, `web/src/test/handlers.ts`.
- Docs: specs, ADR 0206, status, `web/README.md`.
