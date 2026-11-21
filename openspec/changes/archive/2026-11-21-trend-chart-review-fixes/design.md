# Design

## Context

Findings in the PR #14 review; the reviewer reproduced the test gaps with 32 scratch mutants (10 survived).

## Decisions

- **Image plus table, not the Recharts keyboard layer.** One `role="img"` with the totals as its name and a `<details>` table with every bucket: the table is reachable by keyboard and screen reader, readable by sighted users too, and testable through roles. The Recharts layer (arrow keys move the tooltip) would need its own a11y testing and still exposes values only one at a time.
- **Day data derived in the web mock handler**, not a new fixture file: `src/mocks/fixtures/` is a checked snapshot of `contracts/mocks/` (`contracts:check` fails on an extra file) and those mocks are owned by C. The handler sums hourly points per UTC date, the same bucketing the live API is expected to use (to confirm with C, follow-up).
- **Day ticks in UTC, hour ticks local**, with "Dni liczone w czasie UTC." shown under the day view, so the user is told which clock a day uses.
- **Module codes, not names.** The dashboard has no module names to reuse (`FindingsTable` shows `M1`/`M2`/`M3`), so the legend keeps the codes and adds the totals.
- **Lazy `TrendPage`** through `React.lazy` and `Suspense` with the loading text as fallback, wrapped in `SectionBoundary` (an error boundary), because a rejected lazy import otherwise unmounts the whole root.
- **Tooltip test through `defaultIndex`**: jsdom cannot hover an SVG chart, so `TrendChart` takes a test-only `tooltipIndex`, like the test-only `size`.
- **ADR 0203 is not edited.** The review asked for a note there, but `.docs/decisions/README.md` says an accepted ADR is not edited; the measurements are in `.docs/STATUS.md` and this change.

## Risks

- If the live API aligns day buckets to another timezone, the day labels shift by one; tracked in `follow-ups.md` with C.
- The midnight date tick is not guaranteed on the axis: Recharts drops ticks by `minTickGap`, and in zones with a :30 offset no hourly bucket falls on local midnight. The date is always in the tooltip and table; see `follow-ups.md`.
