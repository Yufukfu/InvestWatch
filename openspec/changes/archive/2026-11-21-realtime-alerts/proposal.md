# Proposal

## Why

The challenge asks for real-time alerts when risky content appears, and `web/CLAUDE.md` defines "done" as alerts working. Right now the dashboard learns about new findings only on reload. The contract mock server already emits `finding.created`, `finding.high_risk` and `finding.updated` on Socket.IO `/events`, every 10 s while a client is connected, so the live flow can be built and demonstrated now, without the real backend.

## What Changes

- One Socket.IO connection to namespace `/events` (path `/socket.io`, same origin), opened once for the whole app.
- `finding.created` and `finding.high_risk` refresh the findings list and the summary/trend counts (cache invalidation, no row insertion). `finding.updated` patches the status of that finding in the cached list and detail.
- `finding.high_risk` shows a toast in Polish with the title (as text), module, score and a button that opens the finding's detail panel.
- A live-connection badge in the header (`Na żywo`, `Łączenie…`, `Brak połączenia na żywo`). On every (re)connect the dashboard refetches, because Pub/Sub has no replay (event-relay spec).
- New dependency `socket.io-client` (MIT), recorded in ADR 0208.

Out of scope: `scan.started` / `scan.finished` (no sources view yet), calibration panel, any contract change, browser notifications or sound.

Module: `web/` (Kacper). Uses the existing events of `contracts/schemas/events.schema.json` and `.docs/integration-plan.md` §6; no contract, REST route or event is changed.

## Capabilities

### New Capabilities
- `web-alerts`: the dashboard's real-time connection, cache updates from events, the high-risk toast and the connection indicator.

### Modified Capabilities

## Impact

- Code: new `web/src/features/alerts/`, the URL helper moved from `features/findings/data/useUrlSearch.ts` to `web/src/url/` so alerts can open a finding, `web/src/App.tsx`, styles.
- Dependencies: `socket.io-client` ^4.8.4 (MIT, `npm audit` 0 vulnerabilities).
- Docs: ADR 0208, `.docs/status/dashboard.md`, `web/README.md`, AI log.
