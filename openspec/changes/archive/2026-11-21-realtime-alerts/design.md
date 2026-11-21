# Design

## Context

See proposal.md. Layering ([ADR 0204](../../../.docs/decisions/0204-frontend-architecture.md)): `socket.io-client` may be imported only outside `components/` (oxlint rule), and `.claude/rules/web-dashboard.md` puts the real-time subscription in the `alerts` feature's data layer, one place for all three finding events, with invalidation for `created`/`high_risk` and a cache patch only for `updated`.

## Decisions

- **Socket factory in `features/alerts/data/socket.ts`** wrapping `io(config.eventsUrl, { path: '/socket.io' })`. Tests replace `socket.io-client` with `vi.mock` and drive a fake socket; no network.
- **`useRealtime()` hook** owns the socket in one `useEffect` (created on mount, `disconnect()` on unmount) and the toast list in local state; `AlertsPage` mounted once in the header renders the badge and the toast region. Alternative: RTK listener middleware owning the socket globally; rejected, a hook is easier to test and the app has one mount point.
- **Cache patch** with a thunk: `selectCachedArgsForQuery(state, 'getFindings')`, then `updateQueryData` for each cached list and for `getFindingsById({ id })`; `invalidateTags(['stats'])`. Invalidation for `created`/`high_risk`: `invalidateTags(['findings', 'stats'])`.
- **URL helper moved** to `src/url/useUrlSearch.ts` (shared by findings and alerts) with a `setSearchParam` helper, so `Pokaż` sets `finding=<id>` and the findings page opens the panel from the URL it already reads.
- **ADR 0208** records `socket.io-client`: the API and the mock speak the Socket.IO protocol (python-socketio 5.18.1), so a plain WebSocket or SSE client cannot talk to them without a server change.

## Risks / Trade-offs

- Every `created` event refetches the current list page → acceptable at the mock's 10 s rate and the expected real rate; revisit with debounce if the api emits bursts.
- A patched row may no longer match an active status filter until the next refetch → accepted; the next event or filter change corrects it.
