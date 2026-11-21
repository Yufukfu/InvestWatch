## ADDED Requirements

### Requirement: Generated API client
The dashboard SHALL call the REST API only through the RTK Query client generated from the committed snapshot of `contracts/openapi.yaml`.

#### Scenario: Snapshot in sync
- **WHEN** `npm run contracts:check` runs and `contracts/` has not changed since the last sync
- **THEN** it exits 0

#### Scenario: Snapshot stale
- **WHEN** `contracts/openapi.yaml` or a mock changed and the snapshot was not re-synced
- **THEN** `npm run contracts:check` exits non-zero and names the stale files

### Requirement: Mock mode
The dashboard SHALL render contract mock data without the `api` service, with no change to components.

#### Scenario: Findings from mocks
- **WHEN** the app runs against the mock handlers
- **THEN** the findings table shows the titles from `contracts/mocks/findings.json` as plain text

#### Scenario: API down
- **WHEN** the API is unreachable
- **THEN** the health badge shows "Brak połączenia z API" and the table shows an error message instead of crashing

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
