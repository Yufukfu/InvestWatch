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
| A candidate can shadow a later seed entry with the same URL (`seed` reports `already present` and the row stays an inactive `[candidate]`); let the seed take over an inactive `[candidate] ` row or log which entries a candidate matched | new-item (seed behaviour, decide with the team) |
| A candidate row shows only `[candidate] host`, and the log only a link count, so the approver cannot see where the host came from; log the linking `source_id`s or top document ids | wont-fix (not required by the spec; schema has no column, ADR 0303) |
| `UrlGuard.for_sources` (`targets.py`) compares a registered Unicode host against punycode hosts the same way discovery did before the fix; it predates this change | new-item (scraper, separate fix) |
