## 1. Remove the browser mock mode; MSW only in tests

- [x] 1.1 Write failing tests: a source check that nothing under `src/` (outside `src/test/`) imports `msw` or registers a service worker and that `public/mockServiceWorker.js` is absent; the trend page test that a `bucket=day` response is drawn as returned (no re-aggregation). Verify they fail first.
- [x] 1.2 Remove `src/mocks/browser.ts`, `public/mockServiceWorker.js`, the MSW start-up in `main.tsx`, `config.useMocks`, `VITE_USE_MOCKS`; move handlers to `src/test/handlers.ts` (only health, findings, summary, trend, contract mocks unchanged) and fixtures to `src/test/fixtures/`; update `sync-contracts.mjs` and its test, imports, `Dockerfile`, `.oxlintrc.json`, `.env.example`. Verify tests, lint, typecheck, `contracts:check`, build.
- [x] 1.3 Run the app against `contracts/mock-server` through the Vite proxy and check health, summary, findings and the trend (hour and day) render from the server.
- [x] 1.4 Mutation check; list every mutant and result on this line. Mutants: `main.tsx` imports `msw/browser`; `main.tsx` registers a service worker; `public/mockServiceWorker.js` restored; `src/mocks/` restored; `config.useMocks` restored; `useTrend` re-aggregates points per timestamp. mutations: 6 tried, 6 caught.

## 2. Closing

- [x] 2.1 Apply `iw-docs-update` (web README run steps, ADR 0205 superseding the dev-mock part of ADR 0201, `.docs/STATUS.md` row) and add the `iw-ai-log` row; `docs-check` clean.
- [ ] 2.2 Run `iw-pr-review`; fix real findings.
