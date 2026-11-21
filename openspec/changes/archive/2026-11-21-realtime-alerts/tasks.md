# Tasks

## 1. Live connection and cache updates

- [x] 1.1 Failing tests (fake socket via `vi.mock('socket.io-client')`): one socket to `/events` with path `/socket.io`, state transitions, refetch on connect, invalidation on `created`/`high_risk`, status patch on `updated` in list and detail, malformed payloads ignored, disconnect on unmount.
- [x] 1.2 Add `socket.io-client`, move the URL helper to `src/url/`, implement `socket.ts` and `useRealtime`. `npm test`, lint, typecheck pass; `npm audit` clean.
- [x] 1.3 Mutation check. The count recorded here (16 of 16) was not reproduced by the PR #40 review, which ran 87 mutants with 25 survivors; the gaps are addressed in `realtime-alerts-review-fixes`.

## 2. Toasts and connection badge

- [x] 2.1 Failing component tests: badge texts, toast content as text, `Pokaż` and `Zamknij`, 4-toast limit newest first, dedupe by id, auto-hide after 20 s (fake timers), live region does not take focus.
- [x] 2.2 Implement `LiveBadge`, `AlertToasts`, `AlertsPage`; mount in `App.tsx`; style. Tests pass.
- [x] 2.3 Mutation check. The count recorded here (8 of 8) was not reproduced by the PR #40 review; the meta line was rewritten and cases added for the empty span. Remaining gaps are in `realtime-alerts-review-fixes`.

## 3. Closing

- [x] 3.1 Run against the contract mock server in headless Chrome: badge `Na żywo`, a high-risk toast within ~10 s, `Pokaż` opens the detail, console clean.
- [x] 3.2 Write ADR 0208 (socket.io-client), apply the `iw-docs-update` skill (`.docs/status/dashboard.md`, `web/README.md`, `docs-check` clean) and add the `iw-ai-log` row.
- [x] 3.3 Run the `iw-pr-review` skill and fix real findings (5 findings and 2 test gaps fixed; the count recorded for the review fixes (14 of 14) was not reproduced by the PR #40 review; the rest is in follow-ups.md and `realtime-alerts-review-fixes`).
