# Design

## Context

See proposal.md. The findings are Adam's review of PR #39. Each one was checked against the code at 9386d63 before planning:
- `currentData` makes `rows` undefined during a refetch, which unmounts the table.
- `StatusEditor key={status|note}` re-mounts the editor after a save.
- The `seenQ` resync writes the trimmed text back into the box.
- The debounce timer survives a reset.
- `pushState` runs on every settled search.
- The panel has no isolation of the page behind it.
- `isError` hides the detail.
- The `#8b95a5` border on white is about 2.9:1.

## Decisions

- **Last result while loading:** `useFindings` returns `data` and `total` from `data`, except when `isError`, where both are cleared. The spec still says a failed result is not shown as current. `FindingsTable` shows the loading text only when there are no rows yet, and sets `aria-busy` while a fetch runs. The pager stays mounted because `total` stays defined.
- **Editor state, no re-key:** adjust the state during render when the saved `status`/`note` props change (same pattern as the search box), so the DOM nodes and focus survive. The `role="status"` and `role="alert"` containers are always rendered; their text changes. `onSubmit` returns early while `isSaving`.
- **Search sync:** resync only when `filters.q !== (text.trim() || undefined)`. Reset calls `setText('')` before `onReset`, so the effect's cleanup cancels a pending timer. `setFilters` with only `q` passes `replace` to the URL writer (`history.replaceState`).
- **Modal isolation:** the backdrop and panel render through `createPortal` into a host `div` appended to `document.body`. While mounted, the panel sets `inert` on every other child of `body` and `overflow: hidden` on `body`, and restores both on unmount. Alternative: inert only on `#root`; rejected, because tests render into a plain container and the toasts of #40 would need their own handling anyway.
- **Escape:** in a textarea or input that holds text, the first Escape moves focus to `Zamknij` and keeps the text; Escape from anywhere else closes. This answers both Adam's point (the view can always be closed by keyboard) and the earlier review's (one key must not throw away a note).
- **Refetch failure:** `useFindingDetail` returns `data` when `data.id === id`, so a different id never shows stale detail, together with `isError`. The panel shows the body plus an inline alert when it has a detail and an error, and the full error state only when it has no detail.
- **Contrast:** inputs and chips use `#6b7280` borders (4.8:1 on white, 4.6:1 on `#f8fafc`).
- **Lint:** `react/exhaustive-deps: error` in `web/.oxlintrc.json`. A dry run on the current code found no violations.

## Risks / Trade-offs

- Showing the last rows while loading could be read as stale data. `aria-busy`, the dimmed table and the `Odświeżanie…` hint mark it, and an error clears it.
- `inert` on body children also blocks the toasts of #40 while the panel is open. Accepted: the panel is modal.
