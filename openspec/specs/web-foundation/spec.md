# web-foundation Specification

## Purpose

The foundation of the dashboard (`web/`): an API client generated from the OpenAPI contract that talks only to the backend (the api, or the contract mock server run on its own), a Vitest-only network fake, hardened static delivery behind the HTTPS gateway, and per-module deployment through compose. Feature capabilities (findings, trend, alerts, calibration) build on it.

## Requirements

### Requirement: Generated API client
The dashboard SHALL call the REST API only through the RTK Query client generated from the committed snapshot of `contracts/openapi.yaml`.

#### Scenario: Snapshot in sync
- **WHEN** `npm run contracts:check` runs and `contracts/` has not changed since the last sync
- **THEN** it exits 0

#### Scenario: Snapshot stale
- **WHEN** `contracts/openapi.yaml` or a mock changed and the snapshot was not re-synced
- **THEN** `npm run contracts:check` exits non-zero and names the stale files

### Requirement: Hardened static delivery
The `web` container SHALL serve the build as non-root, on a read-only filesystem, with security headers, behind the HTTPS gateway.

#### Scenario: Security headers
- **WHEN** `/` is requested through the gateway
- **THEN** the response has `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and `Strict-Transport-Security`

#### Scenario: No mock worker in production
- **WHEN** the production image is built
- **THEN** `mockServiceWorker.js` is absent from the served files

### Requirement: Independent deployment
Each module SHALL own its compose file; the root `compose.yaml` SHALL only include them.

#### Scenario: Database without secrets
- **WHEN** `docker compose up` runs without `POSTGRES_ADMIN_PASSWORD` or `POSTGRES_APP_PASSWORD` set
- **THEN** compose refuses to start with an error naming the variable

### Requirement: Presentational feature components
Dashboard feature components SHALL render only from their props, with no store, network call or generated-client access of their own. Each feature SHALL get its data through one data hook that returns plain values and callbacks.

#### Scenario: Component renders from props alone
- **WHEN** a feature component is rendered in a test with props and no store provider
- **THEN** it renders the values it was given, including its loading, error and empty states

#### Scenario: Findings table error state from props
- **WHEN** the findings table is rendered with an error flag and no rows
- **THEN** it shows an alert reading "Nie udało się pobrać zgłoszeń." and no table

#### Scenario: Data hook against the API
- **WHEN** a feature's data hook runs in a test against the Vitest network fake
- **THEN** it returns the rows or values the component needs, taken from the contract mock for that endpoint

#### Scenario: Data hook when the API is unreachable
- **WHEN** a feature's data hook runs and the API request fails
- **THEN** it does not throw: health and findings report an error state that the component shows, and the summary reports no data so its cards are not rendered (unchanged behaviour)

### Requirement: Layering enforced by lint
`npm run lint` SHALL fail when a presentational feature component, at any folder depth under `src/features/*/components/`, imports the API client, a data hook (relative path through a `data` folder), a page component, the store, `react-redux`, `@reduxjs/toolkit` or `socket.io-client`, including their subpaths and imports written with a file extension. `npm test` SHALL fail on the same violations in the real components, so a CI that only runs the tests still enforces the layering.

#### Scenario: Component imports the API client
- **WHEN** a file under `src/features/*/components/` imports from `src/api/`
- **THEN** `npm run lint` exits non-zero and names the restricted import

#### Scenario: Nested component reaches another feature's data hook
- **WHEN** a file in `src/features/*/components/sub/` imports `../../../health/data/useHealth`
- **THEN** `npm run lint` exits non-zero

#### Scenario: Page imported with an extension or a package imported by subpath
- **WHEN** a component imports `../DemoPage.tsx` or `react-redux/es/x`
- **THEN** `npm run lint` exits non-zero

#### Scenario: Data hook imports the API client
- **WHEN** a file under `src/features/*/data/` imports from `src/api/`
- **THEN** `npm run lint` does not report it

#### Scenario: Real components are checked by the tests
- **WHEN** a real component under `src/features/*/components/` imports `src/api/`
- **THEN** `npm test` fails

### Requirement: Data from the backend
The running dashboard SHALL get all data from the backend at `VITE_API_BASE_URL` (default `/api`) through the generated client, with no in-browser fake backend in any build. A fake network SHALL exist only in the Vitest setup, serving the contract mocks unchanged.

#### Scenario: Findings from the backend
- **WHEN** the app runs against a backend that answers `GET /api/findings` with `contracts/mocks/findings.json`
- **THEN** the findings table shows those titles as plain text

#### Scenario: No fake backend in app code
- **WHEN** the shipped files are checked: sources under `web/src/` outside `src/test/` and test files, `web/public/`, the root `*.html`, `*.js`, `*.mjs`, `*.cjs` and `.env*` files
- **THEN** none imports `msw`, imports from `src/test/`, registers a service worker or mentions `useMocks` or `VITE_USE_MOCKS`, and `web/public/` has no `mockServiceWorker.js`

#### Scenario: No browser worker anywhere in src
- **WHEN** every file under `web/src/`, tests and test support included, is checked
- **THEN** none references `msw/browser` or `setupWorker`

#### Scenario: API down
- **WHEN** the API is unreachable
- **THEN** the health badge shows "Brak połączenia z API" and the table shows an error message instead of crashing

#### Scenario: System reported down
- **WHEN** the API answers `/health` with `status: down`
- **THEN** the health badge shows "System nie działa", not the unreachable message
