# Tasks

Rules for every group: `contracts/mocks/`, `contracts/mock-server/` and `registry/seed.csv` are a test double and stay untouched. Tests name `seed.csv` explicitly where they need the fictional firms. Unit tests never touch the network: fetching goes through a `fetcher` the tests replace with saved snapshots in `tests/fixtures/knf/`. The only live check is `pytest -m live`, skipped by default and on CI.

Prerequisite: PR #26 `analytics-worker` and its review fixes are merged, and this branch is rebased on `main` (proposal, Dependencies). If `analytics-m1-m3` landed first, the rebase keeps its `registry.py` methods, and group 3 also applies the short-core guard to its handle identity (design decision 9).

## 1. Snapshots, fetching and parsing (≈ 1.5 h)

- [ ] 1.1 Save trimmed real snapshots (`#entityTable` and pagination kept verbatim, navigation chrome removed) to `tests/fixtures/knf/`: summary, banks, brokerage pages 1-2, branches, no-branch pages 1, 2 and 36, and `?page=99`. Derive the failure fixtures from them (renamed label, missing `entityTable`, empty list, summary without one link). Record the fetch date in a README next to the fixtures.
- [ ] 1.2 Failing tests (`tests/test_knf_parse.py`) for every scenario of the requirements "Fetching the KNF lists" and "Parsing firm records": pagination stop at the clamp page, the 101-page cap, 503 or timeout after 3 attempts, `list_moved`, `layout_changed`, the CERES former name, the PEKAO strike artifact, Admiral Markets → `EE`, unknown country, the malformed record and the 5% limit. Fetching goes through a fake fetcher.
- [ ] 1.3 `knf/fetch.py` (urllib, timeout, user agent, 2 req/s, retries with an injectable sleep) and `knf/parse.py` (`html.parser`, `th`-label mapping, line-aware strike handling, the Polish-to-ISO country map); tests green
- [ ] 1.4 Mutation check; `mutations: N tried, N caught`

## 2. Building the registry: ids, merges, aliases, domains (≈ 2 h)

- [ ] 2.1 Failing tests (`tests/test_knf_build.py`) for "Stable firm ids", "One firm per name", "Generated aliases" and "Firm domains": same ids on reload and reordering, a list move, a rename carried over, the duplicate in one list (`GBR Capital GmbH`), the firm on two lists (`IG Europe GmbH` → `foreign_branch`), a shared core dropped from both firms, `PKO BP` and the brokerage-unit line, trade names without domains, short and stop-list aliases dropped while the full name stays, `50k.trade|50coins.com`, `cysec.gov.cy` excluded, empty domains, a shared domain dropped, a stale manual row
- [ ] 2.2 `knf/build.py` (normalization, uuid5 namespace constant, carry-over from the previous CSV, type precedence, alias generation and filters, `knf/stoplist.txt`, domain extraction and exclusions, the manual-domains merge); tests green
- [ ] 2.3 Mutation check; `mutations: N tried, N caught`

## 3. Matching at real scale (≈ 1.5 h)

- [ ] 3.1 Failing tests (`tests/test_registry.py`) for the new and changed scenarios of "Firm registry matching": `Admiral Markets AS` matched by name, the `EXT Ltd` / `Nova AG` short-core cases (no bare-word or fuzzy match; full name matches), `Wise Asets Europe` still fuzzy, a firm without domains never matched by domain, `_LEGAL_FORMS` pinned by a parametrized list, the 1,000-firm / 20,000-character budget under 1 s. All existing seed scenarios stay green unchanged.
- [ ] 3.2 `registry.py`: longer `_LEGAL_FORMS`, one combined alternation per registry with an alias-to-firm map (same ranking), the short-core guard for bare-word and fuzzy matching, and fuzzy skipped for firms with an exact hit. If `analytics-m1-m3` is on `main`, apply the guard to `_firm_by_handle` and keep its tests green; tests green
- [ ] 3.3 Mutation check; `mutations: N tried, N caught`

## 4. Optional: curated domains for domestic firms (≈ 0.5 h, only if Damian answers yes to open question 1)

- [ ] 4.1 Failing test: every row of `registry/knf_domains_manual.csv` names a firm in `knf.csv`, has `checked_by` and `checked_at`, and its domains are valid hosts that are not social or supervisor hosts
- [ ] 4.2 Damian fills the rows (main site of each brokerage house and bank brokerage unit); the loader merges them; tests green
- [ ] 4.3 Mutation check; `mutations: N tried, N caught` (or `mutations: n/a, data only` if 4.1 is the only code)

## 5. CLI, safe write and the committed registry (≈ 1.25 h)

- [ ] 5.1 Failing tests (`tests/test_knf_cli.py`) for "Writing the registry": column order and sort, the meta file fields, the round-trip through `Registry.from_csv`, `count_dropped` and `--accept-drop`, an interrupted write leaving the old file loadable, a non-zero exit with the right reason for each failure from group 1, the summary (counts, added, removed, renamed, dropped aliases), and the loader never writing `seed.csv`
- [ ] 5.2 `knf/__main__.py` (`--out`, `--previous`, `--accept-drop`, `--verbose`; logs to stderr; temp file and atomic rename); tests green
- [ ] 5.3 Run the loader once against knf.gov.pl by hand (not in tests), review the summary, commit `registry/knf.csv` and `registry/knf.meta.json`; add the `live` marker test
- [ ] 5.4 Mutation check; `mutations: N tried, N caught`

## 6. Default registry and start-up provenance (≈ 1 h)

- [ ] 6.1 Failing tests (`tests/test_worker_config.py`, `tests/test_worker.py`) for "Default registry and provenance at start-up": the default path is `registry/knf.csv` (`test_default_registry_path_is_seed` becomes `…_is_knf`), `registry_loaded` with count and `fetched_at`, `registry_seed` only for the seed, `registry_stale` at 45 days with an injected clock, `registry_unverified` without a meta file, and none of them stopping the worker
- [ ] 6.2 `config.py` default, `worker.py` start-up log, `analytics/Dockerfile` and `analytics/compose.yaml` default `REGISTRY_CSV`, `analytics/.env.example`; check the image still loads the registry (`docker compose run analytics …` or the image's health check); tests green
- [ ] 6.3 Mutation check; `mutations: N tried, N caught`

## 7. Closing

- [ ] 7.1 Apply the iw-docs-update skill: `analytics/registry/README.md` (both files, KNF attribution and link, refresh command), `analytics/README.md` (`REGISTRY_CSV` default), `.docs/analytics-plan.md` §3 (CSV instead of a table, the seed as fixture), ADR 0311 linked from the code comments, your own domain file in `.docs/status/` only if the coordinator asks; add the iw-ai-log row; run docs-check
- [ ] 7.2 Run the iw-pr-review skill and fix real findings
