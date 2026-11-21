# Tasks

Each group from 1 on is one commit. Its first task is the failing test and its last is the mutation check (`iw-commit-cycle` step 3), completed as `mutations: N tried, N caught` (or `mutations: n/a, <reason>`). Group 3 is docs only.

**Starts after `scraper-orchestration` is merged** (it provides `scraper/src/iw_scraper/seed.py` with `seed_knf`, `run_source`, the PostgreSQL `SourceStore` and `UrlGuard.for_sources`). Extend that `seed.py`; do not add a second seed script. Rebase onto `origin/main` first and read the merged `seed.py` and its test (`scraper/tests/test_seed.py`) before writing anything. Tests that touch `sources` run against the compose PostgreSQL (`IW_TEST_*`).

**Loader contract (shared with `scraper-v2-social`, which refers to this note):** `load_seed(path: Path) -> list[SeedEntry]` validates one TOML file; `seed_sources(pool, entries)` writes (URL absent, never overwrite, advisory lock); `main` loads every `*.toml` in `scraper/seeds/`, validates the combined list once, then writes. `platform` defaults to `web` and may be any contract value, so `telegram.toml` (`platform = other`) needs no loader change and no second call in `main`; it only adds the file and a test. Decision 1 in design.md, scenario "Several seed files".

## 1. Seed file, loader and idempotent insert

- [ ] 1.1 Failing tests for every "Seed file is validated before any write" scenario (valid, one invalid entry aborts all, duplicate URL, invalid cron including a six-field one, empty name, non-https, `platform` outside the contract set, `source_kind` outside the contract set) and "Several seed files" (a second file with `platform = other` loads; the same URL in both aborts) and "Entity of unknown registry status", over `load_seed` and the directory scan, which return `SeedEntry` objects without a database
- [ ] 1.2 Add `scraper/seeds/sources.toml` with the 12 entries of design.md decision 9 (exact final URLs from the research report, a comment per entry saying why it is there and which are negative controls) and `load_seed` with the directory scan and validation (`tomllib`, `croniter`, enum values from the `source` contract schema); the 1.1 tests and "Module coverage" and "Registered firm's own page" pass, and a test asserts every `sources.toml` row is `platform = web`
- [ ] 1.3 Failing tests against PostgreSQL for "First run", "Second run", "Dashboard edit survives", "Concurrent runs" (two simultaneous commands) and "Database unreachable" (message holds no connection string), then `seed_sources` in `seed.py` (one transaction, `pg_advisory_xact_lock`, `WHERE NOT EXISTS (url)`, inserted/present report) called from `main` after `seed_knf`; the scenarios pass
- [ ] 1.4 Test (a guard on the file, so it passes at once; prove it by temporarily renaming an M3 row) that every `M3` entry of `sources.toml` has `source_kind = unknown` and "negative control" or "list" in its name ("No named positive chosen"; a human reads the file for named businesses at review). Optional, only if a human names a business from the KNF warnings list before the PR: add it with a comment citing the entry; otherwise the PR body says M3 positives come from `scraper-v2-social` and icobench
- [ ] 1.5 Mutation check; line reads `mutations: N tried, N caught` (guards: each validation rule, the NOT EXISTS clause, the advisory lock, the never-overwrite rule, the accepted `source_kind` set)

## 2. Live check and host guard

- [ ] 2.1 Failing test for "Seed hosts need no extra allow-list entries" (guard built from the seeded rows (as `Source` objects) allows each seeded host and refuses a hop to an unlisted host) with `FETCH_EXTRA_HOSTS` empty; passes once the loader's rows feed `UrlGuard.for_sources`
- [ ] 2.2 Opt-in live check `scraper/tests/test_seed_live.py` (marker `scraper_live`, deselected by default, outside CI): one request per entry through the production fetch path, fails on redirect to another URL, status other than 200, empty text, block or robots refusal, naming the entry and URLs. Written and committed, **run only after a human go-ahead** (it makes real requests to 8 hosts); paste the output in the PR body
- [ ] 2.3 Mutation check; line reads `mutations: N tried, N caught` (n/a for 2.2, which is a live check; guards of 2.1)

## 3. Closing

- [ ] 3.1 Apply the `iw-docs-update` skill: `scraper/CLAUDE.md` and `scraper/README.md` (the seed step and `scraper/seeds/sources.toml`), `.docs/status/scraper.md` (your row; M3 positives come from `scraper-v2-social` and icobench, the KNF-warnings pick is an optional follow-up), `.docs/INDEX.md` if the router needs a "how do I add a source" line, `docs-check` clean, and the `iw-ai-log` row. No new dependency, so no `pip-audit` row; say so in the PR body
- [ ] 3.2 Run the `iw-pr-review` skill and fix real findings; `iw-reviewer` reports no open blocking findings

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
