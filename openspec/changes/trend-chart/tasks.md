## 1. Install Recharts

- [x] 1.1 Test: a smoke test imports `LineChart` from `recharts` and renders it with a fixed size in jsdom (resolves ADR 0203's `ResizeObserver` open point)
- [x] 1.2 (audit: 0 vulnerabilities; bundle baseline 309.72 kB / 98.07 kB gzip, recharts not imported yet, re-measured in group 2: 698.57 kB / 205.98 kB gzip, +389 kB / +108 kB gzip) `npm install recharts react-is` in `web/` (matching React 19); `npm audit` clean; `lint`, `typecheck`, `test` pass; record `vite build` bundle size before and after
- [x] 1.3 Mutation check — mutations: 1 tried, 1 caught

## 2. Trend feature

- [x] 2.1 Test: `TrendChart` with `points` props (no store) shows legend M1/M2/M3, accessible name with totals, empty state, and treats a missing count as 0
- [x] 2.2 `features/trend/components/TrendChart.tsx` and `TrendPoint` prop type
- [x] 2.3 Test: `TrendPage` against the mock handlers shows the chart; `Godzina` pressed by default; `Dzień` sends `bucket=day`; failing request shows the error text; pending shows the loading text
- [x] 2.4 `features/trend/data/useTrend.ts` and `TrendPage.tsx`; mount in `App.tsx`; polish styles for 375, 768 and 1280 px
- [x] 2.5 Mutation check — mutations: 7 tried, 7 caught

## 3. Closing

- [ ] 3.1 Apply the iw-docs-update skill (`.docs/STATUS.md` row, `web/README.md`, docs-check) and add the iw-ai-log row
- [ ] 3.2 Run the iw-pr-review skill and fix real findings
