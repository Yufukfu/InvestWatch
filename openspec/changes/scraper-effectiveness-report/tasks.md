# Tasks

## 1. Report model (pure logic)

- [x] 1.1 Write `scraper/tests/test_report.py` first for `build_report` and the two formatters: window and total counts per source, errors grouped by reason inside the window only, never-run and no-documents lists (active only), unattributed errors, inactive section, empty input (no division by zero), header note about last-run-only, no success-rate field, no `detail` in either format; run it and see it fail for the missing module
- [x] 1.2 Implement `scraper/src/iw_scraper/report.py`: the report dataclasses, `build_report`, the table and JSON renderers (`sys.stdout.write`, no `print`)
- [x] 1.3 Mutation check of the window filter, the active/inactive split and the empty-total guard; record `mutations: N tried, N caught`
  - mutations: 9 tried, 9 caught (window start x2, active/inactive split x2, never-run, no-documents, empty-total guard, unattributed filter, error totals). The row filter on the window is in the SQL and is mutated in 2.3.
- [ ] 1.4 Commit

## 2. Queries and entry point (needs PostgreSQL)

- [ ] 2.1 Extend the tests with the `IW_TEST_PG_DSN` database: rows in the three tables give the expected report; the command writes no row (compare row counts before and after); an unreachable DSN gives an empty stdout, one JSON error line without the password and a non-zero exit; a write on the report's connection is refused; `--since 0`, `-3` and `abc` fail before any connection; a document with a NULL `source_id` and an error with a NULL `source_id` land in the totals and in no source entry; run and see them fail
- [ ] 2.2 Implement the three `SELECT`s inside a read-only transaction, `--since` and `--json` parsing (invalid or non-positive hours is a usage error before any connection), `main()` with `configure_logging()`
- [ ] 2.3 Mutation check of the grouping query, the read-only transaction and the exit code on connection failure; record `mutations: N tried, N caught`
- [ ] 2.4 Commit

## 3. Closing

- [ ] 3.1 Apply the `iw-docs-update` skill: `scraper/README.md` (one short section: command, flags, what it cannot measure), `scraper/CLAUDE.md` module list, `.docs/status/scraper.md`; add the `iw-ai-log` row; `docs-check` prints `docs-check: ok`
- [ ] 3.2 Run the command once against the running stack after a real scan and put the output in the PR body (not in the repo)
- [ ] 3.3 Run the `iw-pr-review` skill and fix real findings
