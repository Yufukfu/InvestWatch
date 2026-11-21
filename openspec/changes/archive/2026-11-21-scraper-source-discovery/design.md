# Design

## Context

See proposal.md for why. Observed on origin/main (2026-11-21):

- `documents.payload` is JSONB and holds `links` as `[{"href": ...}]` (`ingest/store.py` `_PAYLOAD_KEYS`; `document.py` builds it from `ParsedPage.links`, which are absolute http(s) URLs). `documents.source_id` is nullable.
- `sources` has no uniqueness on `url`; `seed.py` inserts with `WHERE NOT EXISTS (SELECT 1 FROM sources WHERE url = $2)`. `Source.collectable` is `active and platform == "web"`; `UrlGuard.for_sources` allows exactly the hosts of collectable sources, so an inactive row widens nothing.
- `PATCH /api/sources/{id}` (`SourcePatch`) accepts `name`, `url`, `target_modules`, `schedule_cron` and `active`. Approval therefore needs no API change. The rest-api spec sentence "only `schedule_cron` may be set to null" is about nullability, not about which fields are patchable; the scenario "Deactivate a source" shows `active` is.
- `scraper-v2-sources` (PR #43) and `scraper-v2-social` are not merged; neither is required. `collect.py`, `app.py` and `__main__.py` are being edited by three other changes, so this change adds only a new module.

## Goals / Non-Goals

**Goals:** a runnable discovery step that proposes new hosts from data we already hold, with a human gate, a per-run cap and no new attack surface.

**Non-Goals:** fetching or scoring candidate pages (the existing pipeline does that after approval); ranking by risk; scheduling the command (a person or a later change runs it); Telegram or other social channel candidates; a dashboard view.

## Decisions

1. **Mine stored links, fetch nothing.** The links are already in `documents.payload`; reading them is a SQL query. *Alternative:* re-fetch the seeded list pages (Moneteo, Comparic, icobench) through the fetch layer. Rejected as the default: it needs new host allowances in the guard, repeats work the collectors did, and adds a fetch path to review. It can be added later as a second candidate source feeding the same insert.
2. **Candidates are ordinary `sources` rows made uncollectable by existing rules.** `active = false` plus `schedule_cron = null` plus `[candidate] ` name prefix. *Alternative:* a new column or table; rejected, the schema is Damian's (ADR 0303) and no contract may change. The prefix is the only marker because `active = false` alone also describes a deactivated real source; the approver renames the row with the same `PATCH`. A candidate a human leaves inactive stays in the table, which is what stops it being proposed again (decision 4).
3. **No auto-activation.** The allow-list is the host set of active web sources, and robots and politeness rules were vetted per host by a person. Auto-activation would let any page we scrape widen what we fetch. Approval is `PATCH {"active": true, "name": ..., "source_kind": ..., "schedule_cron": ...}` in the dashboard or API.
4. **One candidate per host, deduped by host against all sources.** The guard and the domain gate work per host, and a human vets a host, not a URL. The stored URL is the most-linked URL of the host (a proxy for "the page others point at"), cleaned of fragment and `utm_*`, `fbclid`, `gclid`. Host comparison uses the lower-cased hostname with a leading `www.` removed on both sides. Insert uses `WHERE NOT EXISTS (... url = $n)` like `seed.py`; a race with a dashboard `POST` can at worst add a second row for one URL, which a human sees and rejects.
5. **Filters are pure functions over a link list.** A `Candidate` selection function takes `(href, source_modules)` pairs, the set of known hosts and the limit, and returns candidates; SQL and the CLI are thin. This keeps the unit tests free of PostgreSQL. Denylist, in code as a frozen set: social (`facebook.com`, `instagram.com`, `tiktok.com`, `x.com`, `twitter.com`, `t.me`, `youtube.com`, `youtu.be`, `linkedin.com`, `reddit.com`), shorteners (`bit.ly`, `t.co`, `tinyurl.com`, `goo.gl`, `ow.ly`, `is.gd`, `buff.ly`), and trackers (`doubleclick.net`, `googletagmanager.com`, `google-analytics.com`, `googleadservices.com`). Subdomains of a listed host match. URL shape rules mirror the API's `_http_url_as_sent` so a candidate is never a row the API would reject.
6. **Query.** One SQL statement unnests `payload->'links'` for documents with `fetched_at >= now() - since` and returns `(href, source_id)`; the Python side tolerates malformed entries (a non-list `links`, an entry without a string `href`) by skipping them, because `payload` is written by collectors we do not own. Target modules come from a second query over the referenced sources.
7. **Own entry module `iw_scraper.discover`**, `asyncpg` pool from `DATABASE_URL` as in `seed.py`, logging through `configure_logging` and the `logging` module, exit code 1 on a connection or query failure with the DSN redacted by the existing formatter. No `print`.
8. **ADR.** The candidate shape (decisions 2 and 3) is hard to reverse once a dashboard and humans rely on the `[candidate] ` prefix, so it is recorded as an ADR in this change's PR (number taken at apply time, after checking all branches).

## Risks / Trade-offs

- **Noise: the most-linked hosts are often CDNs, news sites or the firm's own subdomains** → denylist, per-run cap, and the human gate; the log shows each candidate with its link count so a reviewer can judge the ranking.
- **`[candidate] ` prefix is a convention, not a constraint** → documented in the ADR and README; a follow-up for Damian could add a typed marker without breaking this change.
- **Link graph is only as rich as what was scraped** → with few sources the output is small; it grows as `scraper-v2-sources` and `scraper-v2-social` documents arrive.
- **Dedup by host hides a better page on a known host** → intended; a human adds more URLs of an approved host directly.
- **Discovery could surface hostile hosts** → they are inert rows until approved, never fetched by this command, and the URL shape filter plus the guard at fetch time still apply.
