# Tasks

## 1. Candidate selection (pure)

- [x] 1.1 Write `scraper/tests/test_discover.py` first (cases from the spec: denylist and subdomains, unsafe URL shapes, tracking strip, one candidate per host with most-linked URL and tie-break, known-host skip with `www.` folding, union of target modules, `["M1"]` fallback, limit and skipped-by-cap count, malformed link entries); run it in the image and confirm it fails because `iw_scraper.discover` is missing
- [x] 1.2 Implement the selection functions in `scraper/src/iw_scraper/discover.py` and verify `test_discover.py` passes
- [x] 1.3 Mutation check: drop each filter, invert the known-host skip, remove the tie-break and the cap in turn, and verify a test goes red each time; record `mutations: N tried, N caught`. Result: `mutations: 20 tried, 20 caught` (a survivor on the backslash check added a test case, then it was caught)

## 2. Database read and insert

- [ ] 2.1 Write the database tests first in `scraper/tests/test_discover_db.py` (real PostgreSQL via `IW_TEST_*`: recent versus old documents, `since` boundary, malformed `payload.links`, orphan document, candidate row shape, rerun inserts nothing, an inactive existing source blocks re-proposal, existing rows untouched); confirm they fail for the missing functions
- [ ] 2.2 Implement the links query, the target-modules lookup and the `WHERE NOT EXISTS` insert; verify the database tests pass
- [ ] 2.3 Mutation check: remove the `fetched_at` bound, the `NOT EXISTS`, and `active = false` from the insert in turn, and verify each makes a test fail; record `mutations: N tried, N caught`

## 3. Command line and reporting

- [ ] 3.1 Write the command tests first (argument parsing for `--since`, `--limit`, `--dry-run`; JSON log lines carry the four counts; dry run inserts nothing; missing `DATABASE_URL` and an unreachable database exit non-zero with no credentials in the output; nothing is written with `print`); confirm they fail
- [ ] 3.2 Implement `main` over the pool and `configure_logging`, and verify the command tests pass
- [ ] 3.3 Run `python -m iw_scraper.discover --dry-run` in the image against a database seeded with a few documents and verify the logged candidates, then run it once for real and once again and verify the second run inserts nothing
- [ ] 3.4 Mutation check: swap dry-run to write, drop the cap in `main`, and verify tests go red; record `mutations: N tried, N caught`

## 4. Closing

- [ ] 4.1 Apply the `iw-docs-update` skill: document the command and the approve-by-PATCH step in `scraper/README.md` and `scraper/CLAUDE.md`, write the ADR (candidate shape and no auto-activation; check the next free number across every branch), update `.docs/status/scraper.md`, add the `iw-ai-log` row, and run `node .claude/skills/iw-docs-update/scripts/docs-check.mjs` until it prints `docs-check: ok`
- [ ] 4.2 Run the `iw-pr-review` skill, fix every real finding, and verify the whole scraper test suite passes in the image

## Workflow follow-up

- Archive the change with `/openspec-archive-change` as the last commit of the branch after the review task is done.
- Follow-ups outside this change: Telegram channel candidates once `scraper-v2-social` merges; a dashboard candidates list (Kacper); optionally a typed candidate marker (Damian).
