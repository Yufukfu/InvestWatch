# Proposal

## Why

The brief (`doc/Opis Wyzwania HackNation UKNF 19.11.pdf`, section 5) asks for the whole stack on-premise "with one command" and the jury judges a demo (sections 6 and 8: "ready for a demo", 30%). Today `docker compose up` on a clean clone starts every service but leaves the database empty: `seed` only registers sources, and a source is scanned when its cron falls due (daily, weekly, every 6 hours) or when someone posts to `POST /api/scans`. The demo rehearsal (issue #78, `.docs/status/scraper.md`) needed 17 hand-made scan requests. A first run must produce documents, findings for M1, M2 and M3, and a calibration curve without a manual step.

## What Changes

- A one-shot `bootstrap` service in `scraper/compose.yaml`, started after `seed` and `worker`: it enqueues one scan request, on the existing `iw:scan-requests` stream, for every active, collectable source that has a cron and never ran (`sources.last_run_at IS NULL`), then exits 0. A source without a cron (the X and YouTube rows) is left for a manual scan: ADR 0109 keeps it manual to protect the dedicated X account and the proxy budget. Scan requests are the one path the queue, per-domain limits, retries and events already handle.
- Idempotent: a restart, `up` on existing volumes or a scale-out enqueues nothing for a source that has run, and nothing twice for one that is still queued. `BOOTSTRAP_SCAN=false` turns it off.
- A read-only readiness command, `python -m iw_scraper.bootstrap status`, prints per source (scanned, failed with reason, pending, or manual) and per stage (documents, findings per module M1 to M3, `calibration_points` per module), and exits non-zero until every module has at least one finding. It is what an operator or the demo checklist runs after `up`: `docker compose run --rm bootstrap python -m iw_scraper.bootstrap status`.
- Quick Start in `README.md` says one command and how to see readiness. `.docs/brief-compliance.md` lists every requirement of the brief with its evidence and its known gaps (Facebook, Instagram and TikTok are not covered, ADR 0103), so "adapt fully to the PDF" is checkable rather than claimed.
- Needs, and does not change, the current defaults: renderer off (`SCRAPER_RENDER_ENABLED`), hosted LLM optional (empty `LLM_BASE_URL` gives rules-only findings).

## Capabilities

### New Capabilities
- `first-run-bootstrap`: what a first `docker compose up` on a clean clone must leave behind (every never-run source scanned, findings for all three modules, calibration points) and how an operator verifies it.

### Modified Capabilities
<!-- none: scraper-deployment's start-order requirements still hold; the new service only adds to them -->

## Out of scope

- New collectors, sources or analytics rules; Facebook, Instagram and TikTok (ADR 0103 stands).
- Any contract, REST route or event: none is touched. `bootstrap` writes the existing `scan_request` message (`contracts/schemas/events.schema.json`).
- X and YouTube collection on first run: those rows stay manual (no cron). Credentials for them or a proxy list: a scheduled source that needs one fails with its normal job error and is reported by `status`, not hidden.
- An offline demo replay (`sample_import` stays a manual tool).
- Module owner: `scraper/` (Adam). `status` reads analytics and api tables read-only; Damian is asked to confirm the table names it relies on in the PR.

## Impact

- `scraper/src/iw_scraper/bootstrap.py` (new), `scraper/compose.yaml`, `scraper/.env.example`, root `.env.example`, `scraper/tests/` (unit, plus a `stack.sh` group).
- `README.md` (Quick Start, Configuration), `scraper/README.md`, `.docs/brief-compliance.md` (new), `.docs/INDEX.md`, `.docs/status/scraper.md`, `openspec/specs/first-run-bootstrap/spec.md` (by archive).
