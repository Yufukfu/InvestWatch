---
paths:
  - "web/**"
---

# Web dashboard rules (module B)

Applies to `web/`. Business contracts are in [`.docs/integration-plan.md`](../../.docs/integration-plan.md) §4 (`Finding`), §5 (REST), §6 (Socket.IO). Calibration: [`.docs/analytics-plan.md`](../../.docs/analytics-plan.md) §8. The mock-first and console rules in [`web/CLAUDE.md`](../../web/CLAUDE.md) also apply.

## Architecture (code quality)

- Layers (decided in [ADR 0204](../../.docs/decisions/0204-frontend-architecture.md)):
  - `src/api/`: the generated client (`generated.ts`) and `baseApi.ts`. `src/store.ts` and the test setup also import it, because they build the store.
  - `src/features/<name>/data/use<Name>.ts`: the feature's data hook. The only feature code that imports `generated.ts`. It calls the generated hooks and returns plain values and callbacks. Real-time (Socket.IO) subscriptions also live here, in the `alerts` feature, because they patch the RTK Query cache.
  - `src/features/<name>/model.ts`: app-owned view-model types, only where the DTO is non-trivial (findings, with `rules`, `firm`, `advertiser`). For a flat DTO (health, summary counts) the hook returns the values the component needs and no mapper is added; a `model.ts` with only the shared prop type is fine, so the data layer never imports from a component.
  - `src/features/<name>/components/`: presentational components. Props in, JSX out. They do not import from `api/`, `data/`, the store or Socket.IO, and do not use the generated DTO types (`Finding`, `Status`, `Module`).
  - `src/features/<name>/<Name>Page.tsx`: calls the data hook and passes its results down as props. This is the only place where data and presentation meet.
- Server state lives in RTK Query (`src/api/baseApi.ts`, generated endpoints). No raw `fetch` in components. Local UI state (open panel, selected row) stays in the component that owns it.
- The component boundary is a CI check: an oxlint `no-restricted-imports` override for `src/features/*/components/**` (in `web/.oxlintrc.json`) rejects `api/`, `data/`, the store, `react-redux`, `@reduxjs/toolkit` and `socket.io-client`. `src/layering.test.ts` runs the real config over sample files and over the real components, so `npm test` alone (CI runs it) fails on a violation. A relative import through any folder named `data` counts as the data layer. A new feature follows the same layout from the start.
- Filter, `sort` and paging state (`page`, `page_size`) use the parameter names of `GET /findings` in `contracts/openapi.yaml`; do not copy the list here. Keep them in the URL search params, so a shared link reproduces the same view.
- Do not compute `risk_level` in the browser. The API derives it from the threshold (§4, ADR 0305). Read it from the response and show it.
- Real-time: subscribe to `finding.high_risk`, `finding.created` and `finding.updated` in one place (a single hook or middleware). `created` and `high_risk` carry only `{id, module, score, title, url, platform}` (integration-plan §6), so invalidate the `findings` and `stats` tags on them rather than inserting rows. Patch the cache only from `finding.updated` (`{id, status}`). `high_risk` drives the toast. Do not keep a second copy of the findings list.
- Charts (trend, calibration curve) use Recharts, a single chart library for the whole app. Chart components take their data as props. They do not fetch.
- A new UI or chart dependency must be open source (MIT, Apache-2.0, BSD or ISC), must pass `npm audit`, and is recorded in an ADR when it is a new choice. The ADR may land before the install PR; the install PR must link it.
- Tests: Vitest with Testing Library for components. Prefer testing presentational components through props, which needs no store setup. Run `npm run lint`, `npm run typecheck` and `npm test` before a commit.

## Presenting risk (what the jury checks)

- Risk information is never hidden. In the finding detail, every rule with `result` `fail` or `uncertain` is visible without an extra click, expand or page change. Its `legal_basis` and `explanation` appear next to it.
- Risk level is shown as text plus colour (`Wysoki`, `Średni`, `Niski`), never colour alone. Badges and risk text meet WCAG AA contrast (at least 4.5:1 for body text).
- Risk text is not smaller than the surrounding body text. Do not use a reduced font size for warnings.
- Layouts are checked at 375 px (phone), 768 px (tablet) and 1280 px (desktop). Table and detail text is not cut off. Wide tables scroll horizontally inside their container instead of clipping.
- Scraped content (`content_excerpt`, `evidence`, `summary`) is rendered as text. Never `dangerouslySetInnerHTML` (oxlint enforces this).
- Render `rule_id` and `name` exactly as the API returns them, for any id. Do not keep a fixed list: the contract allows `R1`–`R18` with `R12a`/`R12b`, and `S1.x` (M1) and `S3.x` (M3) signals (`finding.schema.json`). Do not rename or re-number them in the UI.

## Language

- User-facing texts are Polish. Code, comments, tests and docs are English. Do not mix Polish and English in one visible label.
- Show `legal_basis` in the form the API returns it. Do not translate or rewrite the citation.

## Calibration panel

- The slider previews by choosing points of `GET /calibration`; precision, recall and FP/FN come from those points and are not recalculated in the browser.
- `PUT /settings/thresholds` runs only on an explicit save ("Zapisz"). It recomputes `risk_level` for every finding and changes the threshold that analytics uses for `finding.high_risk` (ADR 0305), so it is a global write, not a preview.
- The generated `putSettingsThresholds` invalidates only the `settings` tag. Override it (`enhanceEndpoints`) so a successful PUT also invalidates `findings`, `stats` and `calibration`.

## Status changes

- Status values are exactly `new | in_review | confirmed | false_positive | closed`. The contract defines no transition graph: offer any of the five and show the API's error if it rejects a change.
- Status changes are keyboard-operable (a native `<select>` or buttons with labels), and the UI shows the saved status after the response, not before.

## Done for web work

- `npm run lint`, `npm run typecheck` and `npm test` pass.
- No `console.log` in the production build.
- Feature works on the mock data from `contracts/mocks/`. Switching to the live `api` needs no component changes.
