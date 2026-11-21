# dashboard (module B)

Frontend: findings table and filters, trend charts, real-time alerts, status changes, and the threshold calibration panel. B also defines the repository structure (team decision), so this directory's layout and stack are B's to confirm.

- Data contract and routes: [`doc/integration-plan.md`](../doc/integration-plan.md) §4 (`Finding`), §5 (REST), §6 (Socket.IO events).
- Calibration panel behaviour: [`doc/analytics-plan.md`](../doc/analytics-plan.md) §8.

## Rules that are easy to get wrong

- Build against mock data that matches the contract from the start; switching to the live `api` must not need component changes. Mocks live in [`contracts/`](../contracts/CLAUDE.md).
- No `console.log` in the production build; the jury checks the browser console.
- User-facing texts are Polish; code, comments and docs are English.
- Alerts arrive over Socket.IO (`finding.high_risk`, `finding.created`, `finding.updated`); the threshold slider must change risk levels and the FP/FN numbers live.
- Scraped text shown in the UI is untrusted: render it as text, never as HTML.

## Done

Filters, trend, status change and alerts work on real data from `api`, and the console is clean.
