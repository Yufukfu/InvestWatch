---
paths:
  - "web/**"
---

# Web dashboard rules (module B)

Applies to `web/`. Business contracts are in [`.docs/integration-plan.md`](../../.docs/integration-plan.md) §4 (`Finding`), §5 (REST), §6 (Socket.IO). Calibration: [`.docs/analytics-plan.md`](../../.docs/analytics-plan.md) §8. The mock-first and console rules in [`web/CLAUDE.md`](../../web/CLAUDE.md) also apply.

## Architecture (code quality)

- Presentational components in `src/features/**` receive data and callbacks through props and import nothing from `api/`, the store or Socket.IO. A feature data hook sits between the API and the components; the layers are in ADR 0204 (PR #11). The existing `FindingsTable`, `SummaryCards` and `HealthBadge` predate that layering and are still to be moved in a refactor change.
- Server state lives in RTK Query (`src/api/baseApi.ts`, generated endpoints). No raw `fetch` in components. Local UI state (open panel, selected row) stays in the component that owns it.
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
