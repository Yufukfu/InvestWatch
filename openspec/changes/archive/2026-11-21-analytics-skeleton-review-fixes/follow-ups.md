# Follow-ups

Out-of-scope reviewer findings and "declined to judge" items, one disposition each.

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | iw-reviewer, whole range | `strat` (genitive plural) is not in `risk_patterns`, so `Ryzyko strat` counts only through `ryzyk` and `Możliwość strat` alone is no warning | `new-item`: widen the `stra…` pattern with a test against the denial list |
| 2 | iw-reviewer, whole range | Capitalised `Art.`, `Ok.`, `Pkt.` still split before a digit | `wont-fix` for now: rare in marketing copy; same as before this change |
| 3 | iw-reviewer, declined | Whether real landing pages end with footer or cookie sentences after the ad label, which would make compliant pages R2 `uncertain` | `new-item`: check on the first real scraped pages; `prominent_sentences` is a YAML param |
| 4 | iw-reviewer, declined | Two firms owning nested domains (`bank.pl`, `bm.bank.pl`) tie on CSV order, not the more specific domain | `wont-fix` for now: no such pair in the registry; revisit with the real KNF loader |
