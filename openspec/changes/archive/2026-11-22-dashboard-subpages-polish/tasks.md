# Tasks

## 1. Sub-pages

- [x] 1.1 Write the failing tests first: per-hash rendering in `App.test.tsx` (only the active page's content in the document, unknown hash falls back), focus and scroll on change, triage and toast action switching to `#zgloszenia`
- [x] 1.2 Implement the page switch in `App.tsx`, a `goToSection` helper in `web/src/url/`, and use it in `useStartTriage` and the realtime `open`
- [x] 1.3 Run typecheck, lint and the suite; check in the browser that back/forward and shared links work
- [x] 1.4 mutations: 8 tried, 8 caught

## 2. UI polish

- [x] 2.1 Write the failing style tests first (no resting underlines, chart-to-disclosure spacing)
- [x] 2.2 Audit every section at 375, 768 and 1280px and restyle dated parts: links, ghost buttons, filters, chips, selects, disclosure, pager, table, drawer, calibration controls
- [x] 2.3 Run typecheck, lint, the suite and the build; confirm no overflow from 320px and a clean contrast test
- [x] 2.4 mutations: 10 tried, 10 caught

## 3. Closing

- [x] 3.1 Apply `iw-docs-update` (`.docs/status/dashboard.md`, specs) and add the AI-log entry
- [x] 3.2 Run the `iw-pr-review` skill and fix real findings (iw-reviewer on `47b00e99..f8f093c1`: no blocking findings; its one "could not check", a focus ring around the script-focused main region, was removed with `main:focus { outline: none }`)
