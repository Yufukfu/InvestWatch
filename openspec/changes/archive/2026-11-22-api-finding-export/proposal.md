## Why

UKNF needs a case file to act on a flagged ad: the URL, a screenshot, the raw page as collected, its `content_hash` and collection time, the failed rules with their legal basis and verified quotes, and the scores and model behind them (issue #70, "fit to the task" criterion). All of it is already stored (`documents`, `findings`, object storage `iw-raw`), but only the dashboard's detail view shows it, without the raw HTML, and nothing gives a supervisor a single printable document.

## What Changes

- **New REST path after the freeze (team's OK needed, version bump):** `GET /findings/{id}/export` in `contracts/openapi.yaml`, `info.version` 1.1.0 → 1.2.0. Read-only and additive; no existing path, response or JSON Schema changes.
- `api/`: the route returns the evidence pack as JSON by default: `finding` (with `risk_level`, scores, model, all rules), `document` (as on the detail, including `scrape_meta.rescan`), `raw` (the HTML from `html_object_key` with its SHA-256 and size, at most the first 2 MB, or `available: false` with a reason), `screenshot_urls` and `failed_rules`. `?format=html` returns the same content as a printable page in Polish: every value escaped, only http(s) URLs as links, a CSP without scripts.
- A store outage degrades only `raw`; an unknown id is 404 (both formats), a malformed id or format is 422.
- Served version becomes `1.2.0`.

Out of scope: `web/` (Kacper's "Eksportuj" button links to `/api/findings/{id}/export?format=html`), the mock server (it has no raw objects; follow-up), PDF output, any scraper or schema change.

Owner: Damian (`contracts/`, `api/`). Consumers: Kacper (`web/`); Adam is asked because the pack exposes the scraper's stored fields and objects.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `rest-api`: a finding's evidence pack, as JSON or a printable HTML page.

## Impact

- Contract: `contracts/openapi.yaml` (new path, `info.version` 1.2.0). No mocks change (no new schema, no new mock file).
- Code: `api/src/investwatch_api/evidence.py` (new), `api/src/investwatch_api/routes/findings.py` (detail body factored into `finding_detail`, the export route), `api/src/investwatch_api/app.py` (version), tests `api/tests/test_export.py`, `api/tests/openapi_check.py` (file refs with a fragment), `api/tests/test_resources.py` (12 paths).
- Team: needs Kacper's and Adam's OK on the new path, asked in the PR; the contract commit uses `IW_CONTRACT_CHANGE=1`.
