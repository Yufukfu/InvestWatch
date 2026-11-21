---
paths:
  - "web/**"
---

# Web dashboard rules (module B)

Applies to `web/`. Business contracts are in [`.docs/integration-plan.md`](../../.docs/integration-plan.md) §4 (`Finding`), §5 (REST), §6 (Socket.IO). Calibration: [`.docs/analytics-plan.md`](../../.docs/analytics-plan.md) §8. The mock-first and console rules in [`web/CLAUDE.md`](../../web/CLAUDE.md) also apply.

## Architecture (code quality)

- Layers (decided in [ADR 0204](../../.docs/decisions/0204-frontend-architecture.md)):
  - `src/api/`: the generated client. Only `src/api/` and `src/features/*/data/` import `generated.ts`.
  - `src/features/<name>/model.ts`: app-owned view-model types. Components do not use the generated DTO types (`Finding`, `Status`, `Module`).
  - `src/features/<name>/data/use<Name>.ts`: the feature's data hook. It calls the generated hooks, maps DTOs to view models, and returns plain values and callbacks.
  - `src/features/<name>/components/`: presentational components. Props in, JSX out. They do not import from `api/`, `data/`, the store or Socket.IO.
  - `src/features/<name>/<Name>Page.tsx`: calls the data hook and passes its results down as props. This is the only layer where data and presentation meet.
- Do not add a container component when a hook does the job. The hook is the boundary.
- Server state lives in RTK Query (`src/api/baseApi.ts`, generated endpoints). No raw `fetch` in components. Local UI state (open panel, selected row) stays in the component that owns it.
- A PR that imports from `api/generated` in a component or uses a DTO type in a component is not ready.
- Filter state (date range, source, `risk_level`, `module`) is one object. It maps 1:1 onto the `GET /findings` query parameters from §5 (`module, status, platform, source_id, risk_level, score_min, date_from, date_to, q`) and is kept in the URL search params, so a filtered view can be shared and reloaded.
- Do not compute `risk_level` in the browser. The API derives it from the threshold (§4, ADR 0305). Read it from the response and show it.
- Real-time: subscribe to `finding.high_risk`, `finding.created` and `finding.updated` in one place (a single hook or middleware). Apply updates to the RTK Query cache (`updateQueryData` or invalidation). Do not keep a second copy of the findings list.
- Charts (trend, calibration curve) use Recharts, a single chart library for the whole app. Chart components take their data as props. They do not fetch.
- A new UI or chart dependency must be open source (MIT, Apache-2.0, BSD or ISC), must pass `npm audit`, and must be recorded in an ADR in the same PR when it is a new choice.
- Tests: Vitest with Testing Library for components. Prefer testing presentational components through props, which needs no store setup. Run `npm run lint`, `npm run typecheck` and `npm test` before a commit.

## Presenting risk (what the jury checks)

- Risk information is never hidden. In the finding detail, every rule with `result` `fail` or `uncertain` is visible without an extra click, expand or page change. Its `legal_basis` and `explanation` appear next to it.
- Risk level is shown as text plus colour (`Wysoki`, `Średni`, `Niski`), never colour alone. Badges and risk text meet WCAG AA contrast (at least 4.5:1 for body text).
- Risk text is not smaller than the surrounding body text. Do not use a reduced font size for warnings.
- Layouts are checked at 375 px (phone), 768 px (tablet) and 1280 px (desktop). Table and detail text is not cut off. Wide tables scroll horizontally inside their container instead of clipping.
- Scraped content (`content_excerpt`, `evidence`, `summary`) is rendered as text. Never `dangerouslySetInnerHTML` (oxlint enforces this).
- Use the 18 rule ids (`R1`–`R18`) and names exactly as the contract provides them. Do not rename or re-number them in the UI.

## Language

- User-facing texts are Polish. Code, comments, tests and docs are English. Do not mix Polish and English in one visible label.
- Show `legal_basis` in the form the API returns it. Do not translate or rewrite the citation.

## Calibration panel

- The threshold control sends the value through `PUT /settings/thresholds`. Precision, recall and FP/FN counts come from `GET /calibration` and are not recalculated in the browser.
- Debounce the slider before sending. Show the response's counts, and update the risk level badges from the refreshed findings data.

## Status changes

- Status values are exactly `new | in_review | confirmed | false_positive | closed`. Offer only transitions the API accepts.
- Status changes are keyboard-operable (a native `<select>` or buttons with labels), and the UI shows the saved status after the response, not before.

## Done for web work

- `npm run lint`, `npm run typecheck` and `npm test` pass.
- No `console.log` in the production build.
- Feature works on the mock data from `contracts/mocks/`. Switching to the live `api` needs no component changes.
