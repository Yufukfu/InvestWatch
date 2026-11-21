# Follow-ups

Items from the reviews that are not part of this change.

| Item | Disposition |
|---|---|
| Telegram, X and YouTube channel candidates need the `scraper-v2-social` collector (links stay denylisted pointers) | new-item (after `scraper-v2-social` merges) |
| A typed candidate marker (column) instead of the `[candidate] ` name prefix; also a unique index on `sources.url` so two discoveries cannot insert one URL twice | new-item (Damian, schema is his, ADR 0303) |
| A dashboard list of candidates with an approve action | new-item (Kacper) |
| `_LINKS` reads every href in the window and filters length in Python | wont-fix (bounded by `--since`; hackathon scale) |
| A failure midway through the inserts logs `discovery failed` without the count written so far | wont-fix (a rerun is safe: known hosts are skipped) |
| Ranking counts links, not distinct documents; the denylist is a code constant | wont-fix (as specified; a product choice) |
| A candidate URL keeps every query parameter except `utm_*`, `fbclid`, `gclid`, so a session or token parameter in a scraped link would be stored in `sources.url` and logged (as the spec says) | new-item (decide a stricter query policy with the team before approving candidates in bulk) |
