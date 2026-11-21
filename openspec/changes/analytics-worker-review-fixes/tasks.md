# Tasks

## 1. Registry warning, honest clean title, test helpers out, main settings

- [x] 1.1 Failing tests: `registry_seed` warning with the default registry and none with `REGISTRY_CSV` set (`config.uses_seed_registry`); clean M2 title names the checked rule ids; importing `investwatch_analytics.worker` loads no `investwatch_analytics.testing`; `Settings.from_env(mapping)` reads the mapping
- [x] 1.2 `config.Settings.from_env(env=None)`, `uses_seed_registry`; worker logs the warning and uses `Settings.from_env(env)` (no `_settings_from`, no `_DEFAULT_REGISTRY` import); `InMemoryStore` and `NoopPublisher` to `investwatch_analytics/testing.py`; M2 clean title; tests green
- [x] 1.3 Mutation check; `mutations: 7 tried, 7 caught`

## 2. Postgres and Redis tests run in CI

- [x] 2.1 `TEST_DATABASE_URL` falls back to `TEST_DATABASE_ADMIN_URL`, `TEST_REDIS_URL` to `IW_TEST_REDIS_URL`; run the suite with only the CI variable names set and confirm 0 skipped (398 passed, 0 skipped)
- [x] 2.2 One-time comparison of `tests/sql/schema.sql` with `alembic upgrade head` (api image) by `pg_dump --schema-only` of `sources`, `documents`, `findings`; record the result in `follow-ups.md` (identical once the mirror took the real, double-prefixed CHECK names; it now uses them)
- [x] 2.3 Mutation check; `mutations: n/a, test configuration only` (no production logic)

## 3. Compose, docs and follow-ups

- [x] 3.1 `analytics/compose.yaml`: `networks: [data]`, a commented `REGISTRY_CSV` slot; README and `.env.example` registry note
- [x] 3.2 `.docs/analytics-plan.md` §4 dedup line, `.docs/security-audit.md` worker entry and fresh `pip-audit`, `.docs/status/platform.md` (stale line, registry note), `.docs/INDEX.md` router row
- [x] 3.3 `follow-ups.md` with every review item and its disposition (KNF loader, URL grouping, threshold crossing on re-analysis, clean pages at score 0, schema drift automation)
- [x] 3.4 Mutation check; `mutations: n/a, docs and config only`

## 5. Linear time on hostile text (second review, required item 4)

- [x] 5.1 Failing tests: splitting `"." + 50 000 spaces`, `". " + 40 000 spaces + "abc"`, an `S.A. Ab` chain, an `ok. 1` chain and a newline + spaces run under 1 s; M2 analysis of 50 000 digits under 3 s; footnote markers with spaces, legal forms and `ok.` cases split as before; a `12,5 %` claim is still R3 (old code: 4-130 s per case)
- [x] 5.2 `preprocessing._BOUNDARY` with possessive `\s++` and a `\s{0,3}` marker gap, abbreviation checks on a 16-character window; R3 claim and exclusion percent patterns `(?<!\d)\d++(?:[.,]\d++)?`; R1-R3 and registry regexes timed on 11 hostile inputs at 20k and 40k characters (all linear after the fix; 1 MB worst case 0.9-17 s); old and new splitter identical on 20 009 texts
- [x] 5.3 Mutation check; `mutations: 10 tried, 8 caught, 2 equivalent` (possessive whitespace and the bounded marker gap each keep the boundary linear alone; reverting both is caught)

## 4. Closing

- [x] 4.1 Apply the iw-docs-update skill (own `.docs/status/platform.md` section, `docs-check` clean) and add the iw-ai-log row
- [ ] 4.2 Run the iw-pr-review skill and fix real findings
