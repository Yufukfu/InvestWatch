# Tasks

## 1. Enqueue never-run sources

- [x] 1.1 Write `scraper/tests/test_bootstrap.py` first and run it red for the intended reason (module missing): active never-run source with a cron gets one `scan_request`; inactive, cron-less (manual) and already-run sources get none; second run adds none; `BOOTSTRAP_SCAN=false` and a non-boolean value; Redis down exits non-zero with nothing enqueued; `XADD` failure removes the idempotency key.
- [x] 1.2 Implement `scraper/src/iw_scraper/bootstrap.py` (`python -m iw_scraper.bootstrap`) with logger JSON output and no `print`; verify `pytest scraper/tests/test_bootstrap.py` is green and `ruff` and the type check pass.
- [x] 1.3 Mutation check (iw-commit-cycle step 3): drop the `last_run_at` filter, the cron filter, the `collectable` filter, the `NX`, the key cleanup, the flag validation and its default, each caught by a test. mutations: 7 tried, 7 caught (an eighth, dropping `OSError` from the Redis handler, survived because redis-py raises `RedisError` subclasses only, so the dead branch was removed; the SQL `active` filter was likewise redundant with `collectable` and removed).

## 2. Readiness command

- [ ] 2.1 Write the `status` tests first (red): complete run exits 0, pending source or missing module exits 1, blocked source listed as `failed`, cron-less never-run source listed as `manual`, exit 0, DB down exits 2 with no stdout, no write happens; plus a test that runs the queries against the migrated schema from `api/migrations`.
- [ ] 2.2 Implement `status` (read-only, JSON on stdout); verify the tests are green and the table names match the migration.
- [ ] 2.3 Mutation check: invert the exit-code rule and drop the module check, both caught; record the line.

## 3. Compose service and stack check

- [ ] 3.1 Add the `bootstrap` one-shot to `scraper/compose.yaml` (scraper image, app role and `REDIS_URL` only, `data` network, hardening, `restart: "no"`, depends on `seed` completed and `worker` healthy) and `BOOTSTRAP_SCAN` to `scraper/.env.example` and the root `.env.example`; verify `docker compose config` for the root file and the documented `-f` chain lists it and shows no `MINIO_*`.
- [ ] 3.2 Add a `scraper/tests/stack.sh` group: clean stack, `bootstrap` exits 0, one stream entry per source, `scan.finished` seen, second `up` adds none; run it and record the output.
- [ ] 3.3 Update `openspec/specs/scraper-deployment` expectations only if the start-order scenarios change (they should not); verify with `openspec validate --strict`.

## 4. Docs and brief traceability

- [ ] 4.1 Write `.docs/brief-compliance.md` from the PDF (modules 1 to 3, sections 3, 5, 6), each row with evidence or a gap; verify every cited path exists and `docs-check` fails when one is broken (try a bad path, then remove it).
- [ ] 4.2 Update `README.md` Quick Start and Configuration (one command, `docker compose run --rm bootstrap python -m iw_scraper.bootstrap status`, `down -v` for a clean demo, `BOOTSTRAP_SCAN`), `scraper/README.md` and `.docs/INDEX.md`; verify the documented commands run as written on a clean clone.
- [ ] 4.3 End-to-end rehearsal on a clean stack from this branch: `up --build`, wait, `status` exits 0; record counts and timings in `.docs/status/scraper.md` with the date and commit.

## 5. Closing

- [ ] 5.1 Apply the iw-docs-update skill (docs, `.docs/status/scraper.md`, no ADR needed) and add the iw-ai-log entry; `docs-check` prints `docs-check: ok`.
- [ ] 5.2 Run the iw-pr-review skill and fix real findings.

## Workflow follow-up

- Archive the change as the last commit; the agent pushes the branch and opens the PR, the human merges.
