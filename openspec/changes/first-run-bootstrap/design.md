# Design

## Context

See proposal.md for why. Facts checked on `origin/main` `daecd965`:

- `seed` registers 19 sources: 17 with a cron (12 web, the KNF row, 4 Telegram) and 2 X and YouTube rows with none, left manual on purpose (`scraper/seeds/*.toml`, ADR 0109). `worker` and `scheduler` wait for `seed` (`scraper/compose.yaml`).
- A manual scan is `XADD iw:scan-requests source_id requested_at`; the worker's consumer group is created from id `0`, so a request enqueued before the worker is up is not lost (`scan_requests.py`).
- `sources.last_run_at` and `last_run_status` are set by `mark_finished` for every ended job, failed ones included (`sources.py`).
- `analytics` and `analytics-eval` start independently of the scraper; analytics reads `iw:documents`, `analytics-eval` fills `calibration_points` from the gold set on `up`.
- The renderer is off and the LLM may be empty by default; both stay as they are.

## Goals / Non-Goals

**Goals:** one `docker compose up` on a clean clone ends with documents, findings for M1 to M3 and calibration points; an operator can verify it with one command; a restart never rescans.

**Non-Goals:** waiting inside `up` for the scans (they take minutes; `up --wait` must stay fast), retrying failed sources, changing the cron of a source, an offline demo mode.

## Decisions

1. **A scraper-side one-shot enqueues the requests; it does not call the API.** `bootstrap` reads `sources` (app role) and `XADD`s the existing `scan_request`. Alternative: `curl POST /api/scans` from a script. Rejected: it needs the api healthy, a route out of `data` for the scraper, and one HTTP call per source for no benefit; the consumer path is the one tested (`scan-orchestration`). Cost: it duplicates the 3-field message shape, which `contracts/schemas/events.schema.json` freezes.
2. **Idempotency by a Redis key per source, not by stream inspection.** `SET iw:bootstrap:<source_id> 1 NX` before each `XADD`; a source with `last_run_at` set is skipped first. Alternative: scan the capped stream (10 000 entries) for the source id, which is O(stream) and wrong once entries are trimmed. The key has no TTL: it lives and dies with the Redis volume, as the stream does. If `XADD` fails after the key was set, the key is deleted again so the next run retries.
3. **Only scheduled sources are bootstrapped; failed first scans are not retried.** A cron-less source was left manual deliberately (X account suspension, proxy traffic), so bootstrap does not override that.  `last_run_at` is set by a failed job too, and a blocked or unconfigured source would otherwise be hammered on every `up`. The scheduler's cron and the dashboard's rescan are the retry paths. `status` makes the failure visible.
4. **`bootstrap` exits when it has enqueued.** It does not wait for the scans: `up --wait` and the 3-minute stack checks stay bounded, and the queue already throttles per domain (`DOMAIN_MIN_INTERVAL_SECONDS`, 5 s). Waiting and judging is `status`, run by a human or `stack.sh`.
5. **`status` reads `documents`, `findings`, `calibration_points`, `job_errors` and `sources` read-only, over one connection.** It runs inside the scraper image, so no new service. The service `command` is the enqueue run; `run` replaces it, so the documented form is `docker compose run --rm bootstrap python -m iw_scraper.bootstrap status`. Readiness means every module has a finding, not a count: counts depend on live pages. Table and column names are taken from `api/migrations/versions` at implementation time and covered by a test against the migrated schema, so a rename breaks the test and not the demo.
6. **Brief traceability is a document, not code.** `.docs/brief-compliance.md` is the table the jury's "conformity to the brief" (20%) can be answered from; `docs-check` already fails on broken relative paths in `.docs/`, which the spec's last scenario relies on (verified when the task is done, by adding a bad path).
7. **No ADR.** Every choice above is reversible by deleting one service and one module; nothing is frozen.

## Risks / Trade-offs

- [All 17 scheduled sources hit the network at once on a cold stack] → the queue's per-domain gate and `SCRAPER_MAX_JOBS` (10) bound it; the XTB crons are staggered for the same reason, and bootstrap requests are not.
- [The venue network blocks scraping] → `status` reports each failure; the fallback stays the manual `sample_import` (documented in the demo checklist, not automated here).
- [Findings need the LLM or the rules-only path to finish] → rules-only is complete without a key; `status` does not require `model.llm`.
- [`status` couples scraper to analytics table names] → test against the real migration (decision 5); Damian confirms in the PR.
- [Re-running after `down` without `-v`] → volumes keep `last_run_at`, so nothing is rescanned and no new findings appear (dedup by `content_hash`, `.docs/status/scraper.md`); a clean demo needs `down -v`, stated in the Quick Start.

- [The scheduler enqueues a cron source in the same minute] → a second scan of one source: the run lock and `content_hash` dedup make it harmless (no duplicate documents).

## Migration Plan

Additive: a new service and CLI, no schema change, no contract change. Rollback: remove the `bootstrap` service; `BOOTSTRAP_SCAN=false` disables it without a redeploy.
