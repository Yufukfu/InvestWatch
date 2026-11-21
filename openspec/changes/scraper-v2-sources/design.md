# Design

## Context

- `sources` (Damian's `0001_initial`) has no unique index on `url`; the contract `source` schema is closed (`additionalProperties: false`), so no new field can ride on a source row without a contract change. See proposal.md for why now.
- `scraper-orchestration` (on its branch, not yet merged) adds `scraper/src/iw_scraper/seed.py`: `seed_knf(pool)` inserts the KNF warnings page with `INSERT ... WHERE NOT EXISTS (url)`, run as `python -m iw_scraper.seed`, and states the rule "a source with the same URL is left alone; the dashboard owns every other edit". It also adds `run_source`, the PostgreSQL `SourceStore` and the `UrlGuard.for_sources` allow-list (host of every collectable source plus `FETCH_EXTRA_HOSTS`, `www.` stripped).
- The web-sources research (this conversation, fetched with our engine, 4 requests per host at most) found 12 pages with HTTP 200, robots allowed and main text in static HTML. It also found that the generic parser works for all of them, so no host parser is needed here.

## Goals / Non-Goals

**Goals:**
- One reviewed, tracked list of sources and one command that puts it into `sources`, safe to run on every `docker compose up` and by several teammates.
- A way to notice a stale seed before the demo.

**Non-Goals:**
- KNF registry parsers and the `registry_*` tables (Damian).
- Rendering, `blocks`, screenshots (`scraper-v3-render`), social platforms (`scraper-v2-social`).
- Updating existing rows from the file, a dashboard sources editor, any `sources` or contract change.

## Decisions

1. **Extend `seed.py`, do not add a second script.** `seed_sources(pool, entries)` sits next to `seed_knf`; `main` runs the KNF seed, then the file. Same dedup rule (URL absent), same exit report. Alternative: a standalone script, rejected as duplicate wiring that task 3.5 of `scraper-orchestration` already built.
2. **Natural key is the URL, not a name or a generated id.** There is no unique index, so the insert is `WHERE NOT EXISTS (url)` inside one transaction that first takes `pg_advisory_xact_lock` on a constant, which serialises concurrent runs (two `INSERT ... WHERE NOT EXISTS` can both pass otherwise). Alternative: ask Damian for a unique index on `url`; rejected for now, because the schema is his, the hackathon is short, and the lock gives the same guarantee for this writer.
3. **Never overwrite.** Matches the KNF seed and the dashboard-owns-edits rule, so a deactivated or retimed source stays that way after a re-seed. The cost: changing a cron in the file does not reach a database that already has the row; that is a dashboard edit or a manual delete.
4. **TOML read with the stdlib `tomllib`, not YAML.** Python 3.12 only, comments are allowed (each entry carries why it is there), and no new dependency to pin and `pip-audit`. The proposal's wording "YAML" was an example.
5. **Validation reuses what exists.** The cron check uses the same `croniter` the scheduler uses (`scraper-orchestration`); the enum values come from the contract `source` schema loaded from `CONTRACTS_DIR`, so a new value there cannot drift from the seed rules.
6. **`render` lives in the file only.** `sources` has no column and the contract is closed, so the flag is a field of the loaded `SeedEntry` (`render: bool = False`) that `scraper-v3-render` imports. `scraper-v3-render` decides how a running worker learns the flag (for example by matching the source URL against the loaded seeds); this change only guarantees the field exists and is optional.
7. **Final URLs only, checked by an opt-in live test.** The research saw redirects (`/pl/oferta` to `/pl/forex`, `/conotoxia/` to `/brokerzy-2/`, an old EY path); a seeded redirect would put a hop through the guards on every run and break the `canonical_url` dedup assumption. The live check (`@pytest.mark.scraper_live`, outside CI, same marker as orchestration's smoke test) needs a human go-ahead because it makes real requests (8 hosts, one request per entry).
8. **No `FETCH_EXTRA_HOSTS` entries.** `for_sources` already allows each source's own host, so the vetted list needs none. Hosts: `www.xtb.com`, `www.mbank.pl`, `moneteo.com`, `comparic.pl`, `takeprofitapp.com`, `www.ey.com`, `grantthornton.pl`, `icobench.com`.
9. **The vetted list** (cron is UTC; XTB entries are staggered by minute so one domain's concurrency cap of 2 and the 5 s request interval are not hit at once):

   | Name | Kind | Modules | Cron | render |
   |---|---|---|---|---|
   | XTB IKE | firm_own | M2 | `0 6 * * *` | yes |
   | XTB IKZE | firm_own | M2 | `10 6 * * *` | no |
   | XTB forex (CFD) | firm_own | M2 | `20 6 * * *` | no |
   | mBank IKE promo 2024 (frozen campaign page) | firm_own | M2 | `0 6 * * 1` | no |
   | mBank IKE eMakler | firm_own | M2 | `0 6 * * *` | yes |
   | Moneteo broker ranking | third_party | M1 | `0 7 * * *` | no |
   | Moneteo XTB review | third_party | M1 | `10 7 * * *` | no |
   | Comparic broker ranking | third_party | M1 | `0 7 * * *` | no |
   | Take Profit broker guide | third_party | M1 | `0 7 * * 1` | no |
   | EY family office (negative control) | third_party | M3 | `0 8 * * 1` | no |
   | Grant Thornton family office (negative control) | third_party | M3 | `0 8 * * 1` | no |
   | icobench Telegram signal groups list | third_party | M1, M3 | `0 8 * * 1` | no |

   URLs are the exact ones from the research report (to be copied into the file in task 1.2 and checked by task 3.2). Do not use `mbank.pl/.../gielda/` (JS-rendered, 2.6k chars of text). Every row says "candidate that matches a signal"; none is a finding about the named business.

## Risks / Trade-offs

- **Page drift:** rankings change monthly (Moneteo) and campaign pages disappear; the live check finds it, the fix is a seed edit plus a manual row change. The mBank 2024 promo page and a weekly cadence reduce the chance during the demo window.
- **Daily cron versus the demo:** a daily schedule shows nothing new in a few hours; the dashboard's manual scan (`POST /api/scans`) is how the demo triggers a run. A shorter demo cadence is a dashboard edit, not a file change.
- **Real businesses as test inputs:** the file and the docs never label a named business as violating anything. Controls are named as controls.
- **M3 is weak** until a human picks real positives from the KNF warnings list (open question 1); two negative controls and a loosely matching list page are what exists.
- **Source kind of unregistered entities:** the contract has no value for "own page of an entity that is not a registered firm", so EY and Grant Thornton are `third_party`; Damian may want a different value (open question 2).
- **Advisory lock** is a constant key shared with nothing else in the scraper; if another writer uses the same key the runs would serialise, which is harmless.

## Open Questions

1. Which 1-2 entities from the KNF public warnings list (`knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne`, 669 entries at research time) are the M3 positives, and do they have a public page that is fetchable? A human chooses (never an agent) and records the name and URL here. Blocks task 1.4 only.
2. Is `third_party` acceptable for M3 pages of entities that are not registered firms, or does Damian want another `source_kind`? (A new value is a contract change; if not wanted, nothing changes.)
3. Should the demo database use a shorter cadence for a few sources (a dashboard edit after seeding), or is manual scan enough?
