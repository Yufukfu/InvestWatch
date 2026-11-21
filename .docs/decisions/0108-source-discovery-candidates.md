# 0108. Source discovery: inactive candidates mined from stored links

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by the human via the `scraper-source-discovery` PR

## Context

Module M1 of the brief is finding ads placed by third parties, but every collected document starts from a URL a human registered. Nothing proposes a new place to look. Constraints that shape any answer:

- The URL guard allows exactly the hosts of collectable sources: `UrlGuard.for_sources` in `scraper/src/iw_scraper/targets.py`, and `Source.collectable` is `active and platform == "web"` (`types.py`). A host is therefore added to what the scraper may fetch by activating a `sources` row, which is the human gate.
- The schema is Damian's ([ADR 0303](0303-database-schema-ownership.md)) and the contracts are frozen, so no column or field can be added. `sources.url` has no unique index (`api/migrations/versions/0001_initial.py`).
- `PATCH /api/sources/{id}` accepts `active`, `name`, `url`, `source_kind`, `target_modules` and `schedule_cron` (`SourcePatch` in `api/src/investwatch_api/models.py`), so a human can approve a row without an API change.
- Every collected page already stores its outbound links in `documents.payload.links` (`[{"href": ...}]`, written by `document.py` and `ingest/store.py`).

## Options considered

1. **Mine the stored links, insert inactive candidates.** Reads data we hold; no fetch, so no new SSRF surface and no change to the guard. Evidence: a run in the test image over a seeded page with five links (two to one finfluencer host, one `t.me`, one `bit.ly`, one broker) logged `links_read=5 hosts_considered=2 inserted=2`, a second run `inserted=0`, and the two rows had `active=false`, `schedule_cron=null`, `source_kind=unknown`.
2. **Re-fetch the seeded list pages (Moneteo, Comparic, icobench) through the fetch layer.** Finds links without relying on past runs, but needs new host allowances in the guard and repeats what the collectors stored. Kept as a possible second feeder of the same insert, not the default.
3. **Insert candidates as active sources.** Rejected: any page we scrape could then widen the set of hosts we fetch, and robots and politeness were vetted per host by a person.
4. **A typed marker for a candidate (new column or table).** Rejected for now: needs a schema change and a contract bump, which the freeze forbids. Marker used instead: `active=false` together with a name starting `[candidate] ` (a deactivated real source is also inactive, so the prefix is what tells them apart).

## Decision

Option 1, with the shape of option 4's workaround: `python -m iw_scraper.discover` reads documents of the last `--since` hours (default 168), keeps links that pass the filters (http or https, no credentials, default port, a DNS name of at least two labels (each at most 63 characters, letters, digits and inner hyphens) with a letter-only TLD, at most 188 characters in all, URL at most 2000, not on the denylist of social, share, shortener and tracker hosts, tracking parameters and fragment removed), proposes one candidate per host that no `sources` row uses yet (active or not, `www.` and a trailing dot folded), most-linked hosts first up to `--limit` (default 20), and inserts each as `platform=web`, `source_kind=unknown`, `active=false`, `schedule_cron=null`, `target_modules` from the linking sources (`["M1"]` for documents without a source), name `[candidate] <host>`. It never updates or deletes a row and never fetches. A human approves with `PATCH /api/sources/{id}` (set `active`, and a real `name`, `source_kind` and `schedule_cron`). A candidate left inactive stays in the table, which is what stops it being proposed again.

The hostname shape and length rules came from the review of this change: the first version let `localhost.`, `facebook.com.`, `0x7f.0x1` and `.example.com` through, and a host long enough to push the name past the API's 200-character `name` limit.

## Consequences

- Easier: discovery grows with the link graph (more when `scraper-v2-sources` and `scraper-v2-social` documents arrive) with no change to the fetch path or the guard.
- Harder: output quality depends on what was scraped, and the ranking counts links, not distinct documents. Noise is bounded by the denylist, the cap and the human gate.
- The `[candidate] ` prefix is a convention. A reviewer or dashboard that lists sources must treat it as "awaiting approval"; a typed marker would need a schema change from Damian and would supersede this ADR.
- No unique index on `sources.url`: two discoveries at the same moment (or one racing a dashboard create) can insert the same URL twice, so run one at a time. A rerun never repeats a host.
- Telegram, X and YouTube links are denylisted: they stay pointers, and a channel candidate needs the social collector of `scraper-v2-social` (a follow-up once it merges).
