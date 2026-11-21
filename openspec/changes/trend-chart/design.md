## Context

`GET /stats/trend` returns `{bucket, points: [{t, M1, M2, M3}]}` (`contracts/openapi.yaml`), already generated as `useGetStatsTrendQuery` with args `module`, `bucket`, `riskLevel`, `dateFrom`, `dateTo`, and served by the mock handlers from `trend.json`. ADR 0203 fixed the library, ADR 0204 the layering. There is no existing chart code.

## Goals / Non-Goals

**Goals:**
- A readable trend chart on mock data and, unchanged, on the live API.
- A chart component that is a pure function of its props, testable without a store.

**Non-Goals:**
- Filters beyond the bucket switch, URL state, the calibration curve, refactoring existing components.

## Decisions

- **Layering per ADR 0204.** `useTrend(bucket)` returns `{ points, isLoading, isError }` as plain values; `TrendChart` receives `points`, `bucket` and `onBucketChange` as props and imports nothing from `api/`, `data/`, the store or the generated DTO types. It declares its own small prop type (`TrendPoint`). `TrendPage` is the only place that joins them. The flat DTO needs no `model.ts`.
- **Line chart, one series per module.** `LineChart` with three `Line`s (`M1`, `M2`, `M3`). Series differ by colour and by stroke dash, and the legend names each series, so meaning never rests on colour alone (web rule on risk presentation applies in spirit; checked at 4.5:1 for text). Counts are integers, so the Y axis uses `allowDecimals={false}`.
- **Bucket switch** is local component state in `TrendPage` (hour/day, default `hour` as in the contract), passed to the hook as the query arg. Native `<button>`s with `aria-pressed`, labelled `Godzina` / `Dzień`. URL search-param state is deferred to the change that adds filters.
- **X axis labels** are formatted from the ISO `t` in the browser's locale (`pl-PL`): `HH:mm` for hour, `d MMM` for day. Time stays UTC in data; display formatting only.
- **Accessibility fallback.** The chart container has `role="img"` and an `aria-label` summarising totals per module; the numbers are not hidden behind hover only.
- **Responsive sizing** uses `ResponsiveContainer`. jsdom has no `ResizeObserver`; component tests either pass a fixed `width`/`height` to the inner chart through a prop or stub `ResizeObserver` in `src/test/setup.ts` (ADR 0203 lists this as unverified; the apply step verifies it and records the result).
- **States.** Loading: `Ładowanie wykresu…`. Error: `Nie udało się pobrać danych trendu.` (the API's failure never crashes the page). Empty `points` (or all zero): `Brak danych w wybranym okresie.` instead of a flat empty chart.
- **No new ADR.** Library choice is ADR 0203; the layout is ADR 0204. Nothing hard to reverse is decided here.

## Risks / Trade-offs

- Recharts is about 8.9 MB unpacked and its production bundle impact is unmeasured → measure with `vite build` before and after and note it in the PR; if large, import only the used components (already named imports, so tree-shaking applies).
- `react-is` must match React 19 → install the version npm resolves for the peer range and let `npm audit` and the typecheck confirm.
- `recharts` 3.x ships its own types; if the TypeScript 7 toolchain objects, fix in the install task rather than adding `@types`.
