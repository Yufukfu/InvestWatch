# Tasks

Rules for every group: `contracts/mocks/`, `contracts/mock-server/` and `registry/seed.csv` are a test double and stay untouched. Tests name `seed.csv` explicitly where they need the fictional firms. Unit tests never touch the network: fetching goes through a `fetcher` the tests replace with saved snapshots in `tests/fixtures/knf/`. The only live check is `pytest -m live`, skipped by default and on CI.

Base: `origin/analytics/analytics-worker` (PR #26), rebased onto each newer tip the coordinator sends; merged only after PR #26 (proposal, Dependencies). If `analytics-m1-m3` landed first, the rebase keeps its `registry.py` methods, and group 3 also applies the short-core guard to its handle identity (design decision 9).

## 1. Snapshots, fetching and parsing (≈ 1.5 h)

- [x] 1.1 Save trimmed real snapshots (`#entityTable` and pagination kept verbatim, navigation chrome removed) to `tests/fixtures/knf/`: summary, banks, brokerage pages 1-2, branches, no-branch pages 1, 2 and 36 (the last; `?page=99` answered the same records). The failure cases (renamed label, missing `entityTable`, empty list, blank names, summary without one link) are derived from them inside the tests. Record the fetch date in a README next to the fixtures.
- [x] 1.2 Failing tests (`tests/test_knf_parse.py`) for every scenario of the requirements "Fetching the KNF lists" and "Parsing firm records": pagination stop at the clamp page, the 101-page cap, 503 or timeout after 3 attempts, `list_moved`, `layout_changed`, the CERES former name, the PEKAO strike artifact, Admiral Markets → `EE`, unknown country, the malformed record and the 5% limit. Fetching goes through a fake fetcher.
- [x] 1.3 `knf/fetch.py` (urllib, timeout, user agent, 2 req/s, retries with an injectable sleep) and `knf/parse.py` (`html.parser`, `th`-label mapping, line-aware strike handling, the Polish-to-ISO country map); tests green
- [x] 1.4 Mutation check; `mutations: 18 tried, 18 caught` (first run 17/18: the end-tag container guard was redundant with the start-tag one, so it was removed and the start-tag mutant is now caught); review fix: `mutations: 7 tried, 7 caught`

## 2. Building the registry: ids, merges, aliases, domains (≈ 2 h)

- [ ] 2.1 Failing tests (`tests/test_knf_build.py`) for "Stable firm ids", "One firm per name", "Generated aliases" and "Firm domains": same ids on reload and reordering, a list move, a rename carried over, the duplicate in one list (`GBR Capital GmbH`), the firm on two lists (`IG Europe GmbH` → `foreign_branch`), a shared core dropped from both firms, `PKO BP` and the brokerage-unit line, trade names without domains, short and stop-list aliases dropped while the full name stays, `50k.trade|50coins.com`, `cysec.gov.cy` excluded, empty domains, a shared domain dropped, a stale manual row
- [ ] 2.2 `knf/build.py` (normalization, uuid5 namespace constant, carry-over from the previous CSV, type precedence, alias generation and filters, `knf/stoplist.txt`, domain extraction and exclusions, the manual-domains merge); tests green
- [ ] 2.3 Mutation check; `mutations: N tried, N caught`

## 3. Matching at real scale (≈ 1.5 h)

- [ ] 3.1 Failing tests (`tests/test_registry.py`) for the new and changed scenarios of "Firm registry matching": `Admiral Markets AS` matched by name, the `EXT Ltd` / `Nova AG` short-core cases (no bare-word or fuzzy match; full name matches), `Wise Asets Europe` still fuzzy, a firm without domains never matched by domain, `_LEGAL_FORMS` pinned by a parametrized list, the 1,000-firm / 20,000-character budget under 1 s. All existing seed scenarios stay green unchanged.
- [ ] 3.2 `registry.py`: longer `_LEGAL_FORMS`, one combined alternation per registry with an alias-to-firm map (same ranking), the short-core guard for bare-word and fuzzy matching, and fuzzy skipped for firms with an exact hit. If `analytics-m1-m3` is on `main`, apply the guard to `_firm_by_handle` and keep its tests green; tests green
- [ ] 3.3 Mutation check; `mutations: N tried, N caught`

## 4. Curated domains for domestic firms (≈ 1 h)

- [ ] 4.1 Failing tests: the manual CSV has the columns `name, website_domains, source_url, verified_by_human`; `verified_by_human` is `true` or `false`; `source_url` is an https URL on one of the row's domains; domains are valid hosts that are not social or supervisor hosts; the merge puts them on the firm, and the meta file counts curated (and unverified) domains apart from KNF ones; a row naming no registry firm fails
- [ ] 4.2 Merge in `knf/build.py`; draft the rows for the 38 domestic firms from official sites checked by hand (the site names the firm and its brokerage activity), all with `verified_by_human` `false`, leaving out a firm whose site cannot be verified; tests green
- [ ] 4.3 Mutation check; `mutations: N tried, N caught`

## 5. CLI, safe write and the committed registry (≈ 1.25 h)

- [ ] 5.1 Failing tests (`tests/test_knf_cli.py`) for "Writing the registry": column order and sort, the meta file fields, the round-trip through `Registry.from_csv`, `count_dropped` and `--accept-drop`, an interrupted write leaving the old file loadable, a non-zero exit with the right reason for each failure from group 1, the summary (counts, added, removed, renamed, dropped aliases), and the loader never writing `seed.csv`
- [ ] 5.2 `knf/__main__.py` (`--out`, `--previous`, `--accept-drop`, `--verbose`; logs to stderr; temp file and atomic rename); tests green
- [ ] 5.3 Run the loader once against knf.gov.pl by hand (not in tests), review the summary, commit `registry/knf.csv` and `registry/knf.meta.json`; add the `live` marker test
- [ ] 5.4 Mutation check; `mutations: N tried, N caught`

## 6. Default registry, start-up provenance and R1 official name (≈ 1.5 h)

- [ ] 6.1 Failing tests (`tests/test_worker_config.py`, `tests/test_worker.py`, `tests/test_rules.py`, `tests/test_registry.py`) for "Default registry and provenance at start-up" and "R1 firm identification": the default path is `registry/knf.csv` (`test_default_registry_path_is_seed` becomes `…_is_knf`), `registry_loaded` with count and snapshot date, no age warning at 45 days, `registry_seed` only for the seed, `registry_unverified` without a meta file, none of them stopping the worker; `find_official_name` on name, name lines and cores only; R1 `uncertain` on an alias-only mention (EFIX/CERES), `pass` when the official form is also present, `pass` on a bank's brokerage-unit line
- [ ] 6.2 `config.py` default, `worker.py` start-up log, `Registry.find_official_name` and R1 in `rules/m2.py`, `analytics/Dockerfile` and `analytics/compose.yaml` default `REGISTRY_CSV`, `analytics/.env.example`; check the image still loads the registry (`docker compose run analytics …` or the image's health check); tests green
- [ ] 6.3 Mutation check; `mutations: N tried, N caught`

## 7. Closing

- [ ] 7.1 Apply the iw-docs-update skill: `analytics/registry/README.md` (the three files, KNF attribution and link, the snapshot date, curated domains and `verified_by_human`, refresh command), `analytics/README.md` (`REGISTRY_CSV` default), `.docs/analytics-plan.md` §3 (CSV instead of a table, the seed as fixture), ADR 0311 linked from the code comments, your own domain file in `.docs/status/` only if the coordinator asks; add the iw-ai-log row; run docs-check
- [ ] 7.2 Run the iw-pr-review skill and fix real findings
