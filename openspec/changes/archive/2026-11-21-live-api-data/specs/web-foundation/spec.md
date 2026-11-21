## REMOVED Requirements

### Requirement: Mock mode
**Reason**: The backend (contract mock server, later `api/`) serves the contract over HTTP, so the web app no longer fakes it in the browser.
**Migration**: Run `contracts/mock-server` (or the api) on `:8000`; `npm run dev` proxies `/api` to it. Use "Data from the backend" below.

## ADDED Requirements

### Requirement: Data from the backend
The running dashboard SHALL get all data from the backend at `VITE_API_BASE_URL` (default `/api`) through the generated client, with no in-browser fake backend in any build. A fake network SHALL exist only in the Vitest setup, serving the contract mocks unchanged.

#### Scenario: Findings from the backend
- **WHEN** the app runs against a backend that answers `GET /api/findings` with `contracts/mocks/findings.json`
- **THEN** the findings table shows those titles as plain text

#### Scenario: No fake backend in app code
- **WHEN** the sources under `web/src/` outside `src/test/` and test files are checked
- **THEN** none imports `msw` or registers a service worker, and `web/public/` has no `mockServiceWorker.js`

#### Scenario: API down
- **WHEN** the API is unreachable
- **THEN** the health badge shows "Brak połączenia z API" and the table shows an error message instead of crashing

#### Scenario: System reported down
- **WHEN** the API answers `/health` with `status: down`
- **THEN** the health badge shows "System nie działa", not the unreachable message
