# Follow-ups

| Item | Source | Disposition |
|---|---|---|
| Confirm with Damian that live `GET /stats/trend` day buckets start at 00:00 UTC and that it returns `{bucket, points}` (one-line integration check at Integration #1) | PR #14 review, design risk | new-item (owner Damian) |
| Midnight date tick not always drawn on the hour axis (Recharts `minTickGap`; :30-offset zones); compute explicit `ticks` if the axis needs the date | iw-reviewer | new-item (owner Kacper) |
| Module display names instead of `M1`/`M2`/`M3` across the dashboard (findings table, trend) | PR #14 review | wont-fix here: the dashboard has no module names yet; a dashboard-wide change |
| Trend filters and URL state | `trend-chart` follow-ups | new-item (owner Kacper) |
| Screen-reader check of the `role="img"` plot and the table in `<details>` on a real browser | iw-reviewer, declined to judge | new-item (owner Kacper) |
