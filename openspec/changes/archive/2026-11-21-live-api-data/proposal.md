## Why

The backend now serves the contract over real HTTP: `contracts/mock-server/` answers every route of `contracts/openapi.yaml` (including `GET /stats/trend?bucket=day`, summed per UTC day on the server) and is the stand-in for `api/` until `api-v1` lands. The dashboard still carries its own in-browser fake backend (MSW service worker, `VITE_USE_MOCKS`) with web-side logic such as summing the hourly trend into days. That duplicates backend behaviour in the web app and lets the dashboard drift from what the backend really returns. The trend chart and every other section must show what the backend sends.

## What Changes

- **BREAKING (dev setup)**: remove the browser mock mode: `src/mocks/browser.ts`, `public/mockServiceWorker.js`, the MSW start-up in `main.tsx`, `config.useMocks` and `VITE_USE_MOCKS`. The app always calls `VITE_API_BASE_URL` (default same-origin `/api`); in dev the Vite proxy forwards it to `API_PROXY_TARGET` (the mock server or the api on `:8000`).
- MSW stays only as the network fake for Vitest. The handlers move to `src/test/handlers.ts`, the contract fixtures to `src/test/fixtures/`, and the handlers keep only the routes the tests use (health, findings, summary, trend), returning the contract mocks as they are, with no web-side aggregation. The day trend is no longer computed in `web/`.
- The Docker build no longer needs to strip a mock worker.
- Docs: `web/README.md` run steps, `contracts/README.md` is unchanged (already describes this setup), ADR 0201 gets a superseding note via a new ADR 0206.

Out of scope: a Socket.IO client and live alerts (separate change), adding the mock server to the root compose (owner of `contracts/`, Damian), the real `api/` REST routes (`api-v1`).

Owner: Kacper (`web/`). Touches no contract, REST route or event; it consumes `GET /health`, `/findings`, `/stats/summary`, `/stats/trend` as they are.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-foundation`: mock mode replaced by "data from the backend"; MSW only in tests.
- `web-trend`: the bucket switch no longer requires web-side day aggregation; day data comes from the backend.

## Impact

`web/src/main.tsx`, `web/src/config.ts`, `web/src/vite-env.d.ts`, `web/src/mocks/` (removed), `web/src/test/`, `web/public/mockServiceWorker.js` (removed), `web/scripts/sync-contracts.mjs` and its test, `web/Dockerfile`, `web/.oxlintrc.json`, `web/.env.example`, tests importing fixtures. Developers must run the mock server (or the api) on `:8000` to see data in `npm run dev`.
