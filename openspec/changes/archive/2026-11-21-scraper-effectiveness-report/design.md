# Design

## Context

All facts already exist: `sources.last_run_status/last_run_at` (written by `scan-orchestration`), `documents` (rows from `document-ingest`) and `job_errors` (`reason`, `source_id`, `occurred_at`; `source_id` has no foreign key on purpose, so errors about unknown sources are kept). The scraper's app role has `SELECT` on all tables. There is no run history table and the schema is Damian's (ADR 0303).

## Goals / Non-Goals

**Goals:**
- One command that answers "what did we collect and what failed" for the demo and the slides.
- Claims only what the data supports.

**Non-Goals:**
- Dashboard, REST route, per-run history, alerting.

## Decisions

1. **Own entry module** `python -m iw_scraper.report`, as `seed.py`: no edit to `collect.py`, `app.py` or `__main__.py`, which other changes touch. It opens one asyncpg connection from `DATABASE_URL`.
2. **Three `SELECT`s, aggregation in SQL, rendering in Python.** Sources joined with grouped document counts; job errors grouped by `(source_id, reason)` inside the window; totals by platform and kind. The queries return plain dicts into a pure `build_report(rows, window)` function, so the formatting and the "never run" or "unattributed" logic are unit-tested without a database; the SQL is tested against the throwaway test schema.
3. **No success rate.** With only the last run stored, a rate would be an invented number. The report shows counts and the last status, and says so in its header. A real rate needs a per-run table, which is a proposal for Damian after the hackathon.
4. **Inactive sources apart.** `active = false` marks sample sets and anything an operator switched off; mixing them into "never run" would make scraper health look worse than it is.
5. **No `detail`, no URLs.** `job_errors.detail` is already redacted but free text; the report needs only `reason`. Sources are shown by id and name, never by URL, so a URL with embedded credentials cannot leak and nothing needs redacting. Reading the connection inside `BEGIN READ ONLY` makes "read-only" a database guarantee instead of a promise.
6. **The window is tested with an injected clock.** `build_report` takes `now`, so the window boundary (inclusive start, errors exactly at the start) is checked without sleeping; documents are windowed on `fetched_at`, job errors on `occurred_at`.
7. **Output.** Table by default, `--json` for slides and scripts, both via `sys.stdout.write` (no `print`); errors via `logging` and `configure_logging()`.

## Risks / Trade-offs

- A window-based error count can hide a source that failed earlier than the window and has not run since; the per-source `last_run_status` and "never run" list cover that.
- `documents` counts grow with the table; the queries group on indexed columns (`source_id`, `fetched_at` has no index, but a hackathon table is small). If it ever matters, the window filter is the first thing to index, in Damian's schema.
- A report only helps if the stack ran long enough to have data; at the demo run it after a scheduled scan.

## Open Questions

- None blocking. Assumed: the jury sees this as terminal output or a slide, not in the dashboard.
