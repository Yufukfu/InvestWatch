# Proposal

## Why

The dashboard lists the first 50 findings in a bare table. The challenge's core use case is an analyst triaging risky content: narrowing the list, reading why a finding is risky and recording a decision. Without filters, detail and status change the dashboard cannot pass Integration #2 ("filters, trend and status change work"). The backend is not run yet (no real data); this change is built and demonstrated on the contract mock server, which already implements the filters, `GET /findings/{id}` and `PATCH /findings/{id}` ([ADR 0206](../../../.docs/decisions/0206-dashboard-data-from-backend.md)).

## What Changes

- Filter bar for the findings list: module, status (multi), risk level, platform, minimum score, date range and text search (`q`), plus sort and paging, all in the URL search params so a link reproduces the view.
- Findings table upgrade: risk level as text plus colour, score bar, status label, sortable score and date columns, empty and error states, a result count, and previous/next paging.
- Finding detail panel opened from a row (`?finding=<id>` in the URL): summary, firm and advertiser, every `fail`/`uncertain` rule visible with `legal_basis`, `explanation` and `evidence`, passing rules grouped below, the document excerpt as text, and the screenshot preview when the document has one.
- Status change and note in the detail panel through `PATCH /findings/{id}`; the UI shows the status the API returned and shows the API's error when it rejects.
- Polish pass on layout (375 / 768 / 1280 px, horizontal scroll inside the table container, WCAG AA contrast).

Out of scope (separate changes): Socket.IO alerts, calibration panel, sources and scans management, any contract edit, running the real api.

Module: `web/` (Kacper). Routes used, all existing in `contracts/openapi.yaml`: `GET /findings`, `GET /findings/{id}`, `PATCH /findings/{id}`, `GET /documents/{id}/screenshot/{viewport}`. No contract, REST route or event is changed.

## Capabilities

### New Capabilities
- `web-findings`: filtering, sorting and paging the findings list, the finding detail with visible risk reasons, and the status change.

### Modified Capabilities

## Impact

- Code: `web/src/features/findings/` (new components, data hooks, URL-state hook), `web/src/styles.css`, `web/src/App.tsx`, tests and `web/src/test/handlers.ts` if the MSW handlers need filter support.
- Dependencies: none (URL state uses the History API; no router added).
- Docs: `.docs/status/dashboard.md`, AI log row; no ADR needed unless the design records one.
