# Follow-ups

| Item | Disposition |
|---|---|
| Lazy-load `TrendPage` (`React.lazy`) so first paint stays near the 98 kB gzip baseline; Recharts adds about 108 kB gzip | new-item |
| `module`, `risk_level`, `date_from`, `date_to` controls on the trend and bucket in URL search params | new-item |
| Live `api` `t` and bucket alignment vs the mock envelope `{bucket, points}` | docs (C owns the contract; confirm at integration) |
| Hourly ticks show `HH:mm` without a date, so a multi-day hourly range repeats labels; add the day to the tick or tooltip | new-item |
