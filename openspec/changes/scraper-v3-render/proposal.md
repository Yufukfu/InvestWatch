# Proposal

## Why

Rules R4-R8 and R13 of the M2 module (font size, contrast, hidden risk text, one-click access, responsiveness, dominance of past results) judge how a page *looks*, and the text we fetch with the TLS client carries no layout. Without rendering they return `not_applicable` ([ADR 0301](../../../.docs/decisions/0301-contracts-v1.md), `.docs/analytics-plan.md` §5), which removes the most visual part of the demo for the UKNF jury. The contract already has `blocks` and `screenshots` and ADR 0301 left the Playwright boundary to this module; the first demo pages (XTB and mBank IKE pages, 300-600 KB of HTML each) are static for text but cannot be judged without layout.

## What Changes

- An optional render step that runs after the normal fetch and parse, only for pages the visual rules apply to (see "Which sources render"): headless Chromium with real device emulation, one fresh browser context per viewport (`desktop`, `tablet`, `mobile`, the contract's names), each with its own viewport, touch and mobile flags and a User-Agent that belongs to the run's identity family.
- Per viewport: a full-page PNG stored in MinIO at `shot/{document_id}/{viewport}.png` (`.docs/integration-plan.md` §2) and `blocks` in the contract's `block` shape (font size and weight, colour and background as `#rrggbb`, bbox, `visible`, `in_viewport_on_load`, `requires_interaction`, `region`, `overflow_clipped`) for R4-R8 and R13.
- The browser is the last rung of the fetch ladder, so it goes through the same guards as `fetch` (URL, port and address guard, `robots.txt`, per-domain rate limit and `Retry-After`, identity and proxy of the run) and every browser request is intercepted: only allowed schemes, ports and public addresses, no other hosts' navigation, no downloads or popups.
- The browser runs in its own container that holds no database, Redis or MinIO credentials and is reachable only from the scraper on a private network (ADR 0105, written in this change with measured image size and pinned versions). The scraper uploads what the renderer returns.
- Render failure never discards the text document: it is ingested without `blocks` and `screenshots` (the visual rules stay `not_applicable`, never a false pass) and the failure is recorded as a job error. A new scraper-side reason `render_failed` covers render problems; blocks, refused targets and storage errors keep their own reasons. `job_errors.reason` is plain `text` in the database (`api/migrations/versions/0001_initial.py`, only a non-empty check), so this needs no migration and no contract change.
- Which sources render: **a domain rule, no per-source field and no host list**. The rules R4-R8 and R13 only apply to a firm's own marketing page, so a source is rendered when its `source_kind` is `firm_own` and its `target_modules` include `M2`. Two deployment settings bound it: `SCRAPER_RENDER_ENABLED` (kill switch, default `false` in code, `true` in the stack's `.env.example`) and `SCRAPER_RENDER_MAX_PER_HOUR` (default 20, one budget shared by all workers). `scraper-v2-sources` sets nothing for rendering: seeding the XTB and mBank rows as `firm_own` + `M2` is enough. Per-source behaviour that is data (a `sources.config` column) is a post-hackathon proposal for Damian, because `sources` has no config column and `source.schema.json` is closed.
- Delivery order, so that a short clock still ends with something demonstrable: desktop and mobile screenshots first, then `blocks`, the tablet viewport last (design, "Order of delivery").
- Out of scope: social posts (no layout, visual rules stay `not_applicable`), OCR of images, replacing the httpx text with the rendered text (`text` and `content_hash` still come from the static parse), JS-only pages, login or consent walls, any change in `analytics/` (Damian consumes `blocks`), the dashboard's screenshot view (route exists in `api/`), sites other than the demo set.
- Owner: Adam's module (`scraper/`), with Damian as consumer of `blocks`.
- Contracts: writes the existing `screenshots` and `blocks` of `ScrapedDocument` v1 and the existing `shot/` key convention; changes none of those shapes. One contract question is raised and left blocked, not decided here: R5 mentions a block covered by another element (sticky bar, banner, overlay) and `block` has no field for it; the proposal is an optional boolean `occluded`, which after Integration #1 needs the whole team and a version bump. It is explicitly deferred: the first release ships without it, nothing else waits for it, and it is not part of this change's done criteria (design, open question 1; tasks, "Deferred follow-up").
- Depends on `scraper-orchestration` being merged (the run that calls the render step) and on `scraper-ingest` (merged, PR #22).

## Capabilities

### New Capabilities
- `page-rendering`: render a collected page in a confined browser and attach per-viewport screenshots and layout blocks to its document.

### Modified Capabilities
- `web-collection`: the closed set of job error reasons gains `render_failed` (a MODIFIED requirement; `scraper-orchestration` adds only the `scan-orchestration` capability and `scraper-v2-social` modifies a different requirement, so there is no clash).

## Impact

- New code under `scraper/` (render client and renderer service, ingest extension for screenshots and blocks, one hook in the run, `Reason.RENDER_FAILED` in `types.py`, a mobile variant of the Chrome identity in `identities.py` that passes `check_pairing`), a second Dockerfile target and a service in the scraper's compose file; pinned dependencies `playwright` (browser version pinned and checksum-verified in the image) and a small HTTP server library for the renderer, `pip-audit` before merge and a row in `.docs/security-audit.md`.
- Docs: `scraper/CLAUDE.md` and `README.md` (new settings, hardware note: the browser image is large), `iw-scraper-conventions` (the render rung), `.docs/decisions/0105-*.md` and its row in the ADR README, `.docs/analytics-plan.md` §5 note that the scraper now delivers `blocks` for the listed hosts, `.docs/status/scraper.md`, AI log row.
- No change to `contracts/`, `api/` or `analytics/`.
