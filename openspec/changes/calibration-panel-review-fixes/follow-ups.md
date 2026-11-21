# Follow-ups

Dispositions: `fix-here`, `new-item` (GitHub issue), `wont-fix` (reason) or `docs`.

| # | Source | Finding | Disposition | Note |
|---|---|---|---|---|
| 1 | review #45, Should fix | `finding.updated` now also invalidates `calibration`, which the API computes by scanning all labelled findings; a burst of status changes causes one scan per event | new-item | Debounce the calibration invalidation (same burst issue as #40). Not done here: it changes the realtime path, which belongs to the alerts work. |
| 2 | review #45, Noted | `findings/data/useFindings.test.tsx` "sends the filters from the URL on the first request" fails with shuffle seeds 2 and 3 (two requests instead of one) | new-item | Order-dependent test from #39 (commit 1307f68). Fix on the #39 branch, not in this PR. |
| 3 | review #45, Noted | The `sync-contracts` test can time out at 5 s under load | new-item | Raise its timeout or make it cheaper; not touched here. |
| 4 | review #45, mutation run | The reviewer's run of 98 mutants left about 27 real survivors; this round covers the ones listed in review item 3 and the guards in `tasks.md` 2.3, not the rest | new-item | Re-run the mutation list on the chart's marker positions, the table column order and the `Zapisano` branches. |
| 5 | review #45, Should fix | Marker label placement is checked by order in a unit test; the rendered positions at 375, 768 and 1280 px are not checked in a browser | new-item | Check the two labels in headless Chrome, as done for the other panels. |
| 6 | this round | Spec `web-calibration` scenarios write thresholds with a decimal point (`0.50`, `0.70`); the panel now shows pl-PL notation (`0,50`) | docs | The requirement names values, not notation. Reword the scenario examples when the spec is next changed (at archive of a later change). |
| 7 | this round | A failed settings read is now shown in the panel; the spec has no scenario for it | docs | Add a scenario to `web-calibration` with the next change to that spec. |
| 8 | approving review #45 | The chart's X-axis tick formatter is not pinned by a test (renders `0,20` in the browser) | new-item | Assert the tick text in a chart test. |
