# 0206. Dashboard data from the backend only; MSW only in tests

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by Kacper via PR
- Supersedes the dev-mode part of [0201](0201-web-stack-and-generated-client.md) ("MSW serves `contracts/mocks` in dev (`VITE_USE_MOCKS=true`)"); the rest of 0201 stands.

## Context

ADR 0201 chose MSW in the browser so `web/` could run before any backend existed. Since then `contracts/mock-server/` (PR #8, spec `openspec/specs/mock-api/spec.md`) serves every route of `contracts/openapi.yaml` under `/api` on `:8000`, with responses validated against the schemas, and Socket.IO on `/events`. It already computes what the browser mock had to fake in `web/`: `GET /stats/trend?bucket=day` sums the hourly series per UTC day on the server (`contracts/mock-server/src/iw_mock_server/app.py`, `stats_trend`), while `web/src/mocks/handlers.ts` repeated that aggregation in TypeScript. Two fakes of one backend can disagree silently, and the dashboard would then show data the real backend never sends.

Checked on 2026-11-21: with the mock server on `:8000`, `npm run dev` proxies `/api/health`, `/findings`, `/stats/summary` and `/stats/trend?bucket=hour|day` to it and gets contract bodies (`vite.config.ts` proxy, unchanged).

## Options considered

1. **Keep browser MSW as an option** (`VITE_USE_MOCKS`). Works offline, but keeps a second fake backend with its own logic and a service worker in dev builds.
2. **Backend only for the running app; MSW only in Vitest.** The app always calls `VITE_API_BASE_URL`; developers run the mock server (or the api). Unit tests still need a network fake and keep MSW with the contract mocks returned unchanged.

## Decision

Option 2. Remove `src/mocks/browser.ts`, `public/mockServiceWorker.js`, the start-up in `main.tsx` and `VITE_USE_MOCKS`. The contract fixtures move from `web/src/mocks/fixtures/` (named in 0201) to `web/src/test/fixtures/`. MSW handlers live in `web/src/test/handlers.ts`, cover only the routes the tests render, and return the contract fixtures (`web/src/test/fixtures/`, still synced by `npm run contracts:sync`) without computing anything the backend owns. `web/src/noBrowserMocks.test.ts` fails if app code imports `msw` or registers a service worker again.

## Consequences

- One source of data behaviour (the backend); the trend's day buckets come from the server.
- `npm run dev` shows data only with the mock server or the api on `API_PROXY_TARGET` (default `http://localhost:8000`); without it the dashboard shows its "API unreachable" states.
- A browser that ran the old mock mode on the same origin keeps the registered worker until it is unregistered (DevTools, Application, Service Workers) or the site data is cleared.
- The mock server is not in the root `compose.yaml`; adding it (or pointing `API_UPSTREAM` at it) is Damian's call in `contracts/`.
