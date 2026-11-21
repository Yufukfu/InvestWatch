# Design

## Context

Findings in the PR #14 review; the reviewer reproduced the test gaps with 32 scratch mutants (10 survived).

## Decisions

- **Image plus table, not the Recharts keyboard layer.** One `role="img"` with the totals as its name and a `<details>` table with every bucket: the table is reachable by keyboard and screen reader, readable by sighted users too, and testable through roles. The Recharts layer (arrow keys move the tooltip) would need its own a11y testing and still exposes values only one at a time.
- **Day data derived in the web mock handler**, not a new fixture file: `src/mocks/fixtures/` is a checked snapshot of `contracts/mocks/` (`contracts:check` fails on an extra file) and those mocks are owned by C. The handler sums hourly points per UTC date, the same bucketing the live API is expected to use (to confirm with C, follow-up).
- **Day ticks in UTC, hour ticks local**, with "Dni liczone w czasie UTC." shown under the day view, so the user is told which clock a day uses.
- **Module codes, not names.** The dashboard has no module names to reuse (`FindingsTable` shows `M1`/`M2`/`M3`), so the legend keeps the codes and adds the totals.
- **Lazy `TrendPage`** through `React.lazy` and `Suspense` with the loading text as fallback.

## Risks

- If the live API aligns day buckets to another timezone, the day labels shift by one; tracked as a follow-up with C.
