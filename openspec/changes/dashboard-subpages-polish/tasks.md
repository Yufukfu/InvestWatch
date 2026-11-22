# Tasks

## 1. Sub-pages

- [ ] 1.1 Write the failing tests first: per-hash rendering in `App.test.tsx` (only the active page's content in the document, unknown hash falls back), focus and scroll on change, triage and toast action switching to `#zgloszenia`
- [ ] 1.2 Implement the page switch in `App.tsx`, a `goToSection` helper in `web/src/url/`, and use it in `useStartTriage` and the realtime `open`
- [ ] 1.3 Run typecheck, lint and the suite; check in the browser that back/forward and shared links work
- [ ] 1.4 mutations: N tried, N caught

## 2. UI polish

- [ ] 2.1 Write the failing style tests first (no resting underlines, chart-to-disclosure spacing)
- [ ] 2.2 Audit every section at 375, 768 and 1280px and restyle dated parts: links, ghost buttons, filters, chips, selects, disclosure, pager, table, drawer, calibration controls
- [ ] 2.3 Run typecheck, lint, the suite and the build; confirm no overflow from 320px and a clean contrast test
- [ ] 2.4 mutations: n/a or N tried, N caught

## 3. Closing

- [ ] 3.1 Apply `iw-docs-update` (`.docs/status/dashboard.md`, specs) and add the AI-log entry
- [ ] 3.2 Run the `iw-pr-review` skill and fix real findings
