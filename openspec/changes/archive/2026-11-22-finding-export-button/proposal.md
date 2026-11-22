# Proposal

## Why

A UKNF supervisor needs a one-click case file for a finding (issue #70). The api serves it since #104 (`GET /api/findings/{id}/export`, contract 1.2.0) and the mock server since #109; the dashboard has no way to reach it yet.

## What Changes

- The finding detail header gets an `Eksportuj` link (styled as a button) next to `Zamknij`. It opens `<VITE_API_BASE_URL>/findings/{id}/export?format=html` in a new tab: the printable Polish evidence pack the api renders. The URL is built in the data hook (`useFindingDetail`) from the app's API base, so it goes through the dev proxy (mock or live api) and through the gateway in docker with no component change.
- The link is shown only when a finding's detail is loaded (not while loading, not on 404).
- `web/src/api/openapi.json` and `generated.ts` are regenerated from `contracts/openapi.yaml` 1.2.0 (`npm run api:generate`), so `contracts:check` is clean again. The generated `getFindingsByIdExport` query is not used: the page is a navigation, not an RTK Query fetch.

Out of scope: a JSON download button (the JSON pack stays available at the same URL without `format`), PDF, any change to the export itself.

Module: `web/` (Kacper). Touches no contract: it consumes the existing REST route `GET /findings/{id}/export` (contracts 1.2.0). No event changes.

## Capabilities

### New Capabilities

### Modified Capabilities

- `web-findings`: adds a requirement for the export link; the "Bare URL in evidence" scenario now lists the export link among the detail's links.

## Impact

- Code: `web/src/features/findings/model.ts`, `data/useFindingDetail.ts`, `components/FindingDetailPanel.tsx`, `web/src/styles.css`, the generated client snapshot, and tests.

Spec pre-approved by Kacper via the issue request.
