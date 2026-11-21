# Design

## Context

- `sources` (Damian's `0001_initial`) has no unique index on `url`; the contract `source` schema is closed (`additionalProperties: false`), so no new field can ride on a source row without a contract change. See proposal.md for why now.
- `scraper-orchestration` (on its branch, not yet merged) adds `scraper/src/iw_scraper/seed.py`: `seed_knf(pool)` inserts the KNF warnings page with `INSERT ... WHERE NOT EXISTS (url)`, run as `python -m iw_scraper.seed`, and states the rule "a source with the same URL is left alone; the dashboard owns every other edit". It also adds `run_source`, the PostgreSQL `SourceStore` and the `UrlGuard.for_sources` allow-list (host of every collectable source plus `FETCH_EXTRA_HOSTS`, `www.` stripped).
- The web-sources research (this conversation, fetched with our engine, 4 requests per host at most) found 12 pages with HTTP 200, robots allowed and main text in static HTML. It also found that the generic parser works for all of them, so no host parser is needed here.

## Goals / Non-Goals

**Goals:**
- One reviewed, tracked list of sources and one command that puts it into `sources`, safe to run repeatedly and by several teammates (it is a manual command, `python -m iw_scraper.seed`; no compose service runs it).
- A way to notice a stale seed before the demo.

**Non-Goals:**
- KNF registry parsers and the `registry_*` tables (Damian).
- Rendering, `blocks`, screenshots (`scraper-v3-render`), social platforms (`scraper-v2-social`).
- Updating existing rows from the file, a dashboard sources editor, any `sources` or contract change.

## Decisions

1. **Extend `seed.py`, do not add a second script.** `seed_sources(pool, entries)` sits next to `seed_knf`; `main` runs the KNF seed, then the seed files. Same dedup rule (URL absent), same exit report. The optional `CRON` argv of `python -m iw_scraper.seed` stays the KNF row's only. Alternative: a standalone script, rejected as duplicate wiring that task 3.5 of `scraper-orchestration` already built.

   **Loader contract (agreed with `scraper-v2-social`, which seeds `telegram.toml` through it).** `load_seed(path: Path) -> list[SeedEntry]` reads and validates one file; `seed_sources(pool, entries)` writes. `main` loads every `*.toml` in the seeds directory (`scraper/seeds/`, found relative to the package, copied into the image with `scraper/`), concatenates the entries, validates the whole list once (so a URL repeated across files is a duplicate) and only then writes. One function per file plus a directory scan is the simplest form: a new seed file needs no code edit and no second call in `main`. Each entry has `platform` (default `web`, any value of the contract `platform` enum), so `telegram.toml` can say `platform = other` (the enum has no `telegram` value and the contract is frozen: issue #34 keeps `other` until contract v2, so the loader reads the enum and never hard-codes it); this file's own test asserts all its rows are `web`.
2. **Natural key is the URL, not a name or a generated id.** There is no unique index, so the insert is `WHERE NOT EXISTS (url)` inside one transaction that first takes `pg_advisory_xact_lock` on a constant, which serialises concurrent runs (two `INSERT ... WHERE NOT EXISTS` can both pass otherwise). Alternative: ask Damian for a unique index on `url`; rejected for now, because the schema is his, the hackathon is short, and the lock gives the same guarantee for this writer.
3. **Never overwrite.** Matches the KNF seed and the dashboard-owns-edits rule, so a deactivated or retimed source stays that way after a re-seed. The cost: changing a cron in the file does not reach a database that already has the row; that is a dashboard edit or a manual delete.
4. **TOML read with the stdlib `tomllib`, not YAML.** Python 3.12 only, comments are allowed (each entry carries why it is there), and no new dependency to pin and `pip-audit`. The proposal's wording "YAML" was an example.
5. **Validation reuses what exists.** The cron check uses the same `croniter` the scheduler uses (`scraper-orchestration`); `croniter.is_valid` accepts six fields, so the loader also requires exactly five; the enum values (`platform`, `source_kind`, modules) come from the contract `source` schema loaded from `CONTRACTS_DIR`, so a new value there cannot drift from the seed rules.
6. **No render flag in the seed.** `sources` has no column and the contract is closed, so a flag could only live in this file. `scraper-v3-render` decides by rule instead (`source_kind = firm_own` and `M2` targeted), because R4-R8 and R13 only apply to firms' own marketing pages. The five XTB and mBank M2 rows below are therefore its demo set with no field here. Alternative: a `render` field in `SeedEntry`, rejected as per-source behaviour that would need a contract change to reach the dashboard later.
7. **Final URLs only, checked by an opt-in live test.** The research saw redirects (`/pl/oferta` to `/pl/forex`, `/conotoxia/` to `/brokerzy-2/`, an old EY path); a seeded redirect would put a hop through the guards on every run and break the `canonical_url` dedup assumption. The live check (`@pytest.mark.scraper_live`, outside CI, same marker as orchestration's smoke test) needs a human go-ahead because it makes real requests (8 hosts, one page request per entry plus its `robots.txt`).
8. **No `FETCH_EXTRA_HOSTS` entries.** `for_sources` already allows each source's own host, so the vetted list needs none. Hosts: `www.xtb.com`, `www.mbank.pl`, `moneteo.com`, `comparic.pl`, `takeprofitapp.com`, `www.ey.com`, `grantthornton.pl`, `icobench.com`.
9. **The vetted list** (cron is UTC; XTB entries are staggered by minute so one domain's concurrency cap of 2 and the 5 s request interval are not hit at once):

   | Name | Kind | Modules | Cron |
   |---|---|---|---|
   | XTB IKE | firm_own | M2 | `0 6 * * *` |
   | XTB IKZE | firm_own | M2 | `10 6 * * *` |
   | XTB forex (CFD) | firm_own | M2 | `20 6 * * *` |
   | mBank IKE promo 2024 (frozen campaign page) | firm_own | M2 | `0 6 * * 1` |
   | mBank IKE eMakler | firm_own | M2 | `5 6 * * *` |
   | Moneteo broker ranking | third_party | M1 | `0 7 * * *` |
   | Moneteo XTB review | third_party | M1 | `10 7 * * *` |
   | Comparic broker ranking | third_party | M1 | `0 7 * * *` |
   | Take Profit broker guide | third_party | M1 | `0 7 * * 1` |
   | EY family office (negative control) | unknown | M3 | `0 8 * * 1` |
   | Grant Thornton family office (negative control) | unknown | M3 | `0 8 * * 1` |
   | icobench Telegram signal groups list (list page) | unknown | M1, M3 | `0 8 * * 1` |

   URLs are the exact ones from the research report (to be copied into the file in task 1.2 and checked by task 2.2). Do not use `mbank.pl/.../gielda/` (JS-rendered, 2.6k chars of text). The M3 rows carry "negative control" or "list" in their name (task 1.4 checks it). Every row says "candidate that matches a signal"; none is a finding about the named business.

## Risks / Trade-offs

- **Page drift:** rankings change monthly (Moneteo) and campaign pages disappear; the live check finds it, the fix is a seed edit plus a manual row change. The mBank 2024 promo page and a weekly cadence reduce the chance during the demo window.
- **Daily cron versus the demo:** a daily schedule shows nothing new in a few hours; the dashboard's manual scan (`POST /api/scans`) is how the demo triggers a run. A shorter demo cadence is a dashboard edit, not a file change.
- **Real businesses as test inputs:** the file and the docs never label a named business as violating anything. Controls are named as controls.
- **M3 positives live elsewhere:** this file holds two negative controls and a loosely matching list page; the demo's M3 positives are the Telegram paid-signal channels seeded by `scraper-v2-social`. Naming a business from the KNF warnings list stays an optional, human-only follow-up.
- **`unknown` for M3 pages:** the scraper cannot determine registry status, so it does not claim `third_party` or `firm_own` for those pages; analytics routes M3 by registry mismatch. `unknown` is in the contract enum, the `source` schema and the `ck_sources_source_kind` check, so no contract or migration change is needed.
- **Advisory lock** is a constant key shared with nothing else in the scraper; if another writer uses the same key the runs would serialise, which is harmless.

## Open Questions

1. Optional follow-up, not blocking: which entity (if any) from the KNF public warnings list (`knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne`) does a human want added as a named M3 positive, and does it have a fetchable public page? A human chooses (never an agent) and records the name and URL here.
2. Should the demo database use a shorter cadence for a few sources (a dashboard edit after seeding), or is manual scan enough?
