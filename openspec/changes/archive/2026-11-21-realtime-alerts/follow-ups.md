# Follow-ups: realtime-alerts

From the whole-branch `iw-reviewer` pass. Fixed in this branch: transports (polling fallback), held toasts and the announcement line, UUID ids, refresh on a high-risk event without a title, the bundle size in the status file, the per-refresh screen-reader announcement, long titles clamped, two toasts at most on phones, and an integration test for the row update and `Pokaż`.

| Item | Disposition |
|---|---|
| Double fetch on the first connect (initial query, then the connect refetch) | wont-fix: the spec requires a refetch on every connect; one extra GET per page load |
| A patched row may no longer match the active status filter | wont-fix: accepted in design.md, the next refresh corrects it |
| Bursts of `finding.created` each refetch the list | new-item: debounce invalidation if the real api emits bursts (design.md risk) |
| An open StatusEditor draft is reset when `finding.updated` arrives for the same finding | wont-fix: another tab saved first; the form shows the saved value. Revisit with a notice if analysts work in parallel |
| Caddy forwarding the WebSocket upgrade on `/socket.io` is not exercised in tests | new-item: cover in the compose smoke test when the api is wired into compose |
