# Design

## Context

- `scraper-v1` fetches with `noble-tls` (ADR 0101) and parses with `lxml`; `scraper-ingest` stores the raw HTML at `html/{id}.html` before the insert and removes it when the insert certainly did not commit (`ingest/pipeline.py`); `scraper-orchestration` adds `run_source`, the run that joins guards, fetch, parse and ingest. Playwright is the last rung of the ladder (`iw-scraper-conventions`).
- Contract (v1, `contracts/schemas/scraped-document.schema.json`): `screenshots` is `{desktop, tablet, mobile}` of object keys or null; `blocks` is a list of `block` (required `viewport, text, font_size_px, visible`; optional `tag, font_weight, color, background_color, bbox, in_viewport_on_load, requires_interaction, region, overflow_clipped`); `scrape_meta` accepts extra keys. `analytics/` declares `blocks` in its model but nothing consumes it yet; `api/` already serves `GET /documents/{id}/screenshot/{viewport}` from the `documents.payload.screenshots` key.
- `sources` has no config column and `source.schema.json` has `additionalProperties: false`: no per-source setting can be stored without a contract change and an Alembic revision (Damian).
- The scraper runtime image is 254 MB (`iw-scraper:rt`, measured locally); the latest `playwright` on PyPI is 1.60.0 (`pip index versions playwright`, 2026-11-21); Microsoft publishes `mcr.microsoft.com/playwright/python` images. The Chromium and system-library size is not measured yet; task 1.1 measures it and ADR 0105 records it.
- Network model (`infra/README.md`): `data` is internal (Postgres, Redis, MinIO), `egress` reaches the internet; a module may declare its own private network in its compose file.
- Demo set for the visual rules: XTB IKE and IKZE pages and the mBank IKE pages, static HTML of 300-600 KB whose layout cannot be recovered from text (research by the sources probe, 2026-11-21).

## Goals / Non-Goals

**Goals:**
- Deliver `blocks` and `screenshots` for the demo pages so R4-R8 and R13 can run on real material.
- Keep the browser, which executes hostile page code, away from every secret and every internal service.
- Keep the text pipeline unchanged: a render problem must never lose or change a document.

**Non-Goals:**
- Rendering as a fallback for JS-only pages or bot walls (a different reason to use the last rung; not needed for the demo).
- Pixel analysis, OCR, or judging the rules (analytics' job).
- A per-source render switch (contract question) and rendering social posts.

## Decisions

1. **Separate renderer image and service, scraper stays Playwright-free.** Options: (A) Playwright and Chromium inside the scraper image: one image, simple calls, but the browser then runs next to `DATABASE_URL`, `REDIS_URL` and `MINIO_*` and grows a 254 MB image by the browser and its libraries. (B) a separate image with a small HTTP service the scraper calls: the browser holds no secrets, own base image and update cadence, own limits. (C) a separate arq worker on a `render` queue: needs `REDIS_URL` in the browser container, which is exactly what we avoid. Decision: B, recorded as ADR 0105 with the measured sizes (task 1.1). The renderer gets `target`, the run's identity and proxy, and returns JSON with the blocks and base64 PNGs; the scraper uploads to MinIO and inserts. The proxy URL travels only in the request body over the private network, is never logged, and is not stored.
2. **Hook, not a rewrite of the run.** After parse and before `Ingestor.ingest`, `run_source` calls `render_page(...)` when the source qualifies (`SCRAPER_RENDER_HOSTS` and `M2`), and passes the result in the `page` dict (`page["render"]`: blocks, PNG bytes, meta). Ingest uploads the PNGs next to the HTML, sets `screenshots` and `blocks` on the document before validation, and cleans up on duplicate or failed insert exactly as it does for HTML. The one hook in `run_source` and the extension of `Ingestor` are the only edits to orchestration and ingest code; both are additive and gated by `page.get("render")`.
3. **Guards split by who owns the state.** The scraper owns `robots.txt`, the per-domain rate limit, `Retry-After`, failure pause and identity draw (Redis state, run context) and applies them before calling the renderer, which counts as one request for the domain. The renderer is stateless and enforces confinement inside the browser: it reuses `iw_scraper.targets` (`UrlGuard`, `AddressGuard`) to check every browser request, with the source host and the ports passed per call. Tests inject a resolver or `internal_hosts` so a local fixture server passes, as in the fetch tests.
4. **One navigation, three viewports by resizing.** One page load is one polite request and one set of scripts; each viewport sets the size, waits for layout to settle and measures. Trade-off: a site that serves different markup by User-Agent or client hints is measured with the desktop markup at mobile width (a documented limitation, open question 4), and `matchMedia`-driven changes are seen because the browser fires resize.
5. **Measure in the page with one script, text stays verbatim.** A single `page.evaluate` script walks the DOM once per viewport, takes the nearest block-level element that owns text, reads `getComputedStyle` and `getBoundingClientRect`, composites alpha colours over the nearest opaque ancestor background (`null` when it is an image or gradient), and classifies `visible`, `requires_interaction` and `region` with the rules in the spec. Heuristics for `legal` and interaction are word and attribute lists in one module so they are testable and extendable; footnote markers (`*`, `¹`) stay a text decision for analytics (R6 reads the text), not a flag here. The script is a small `.js` file in the renderer package, without `console.log`.
6. **`text` stays the static parse.** The render supplies layout, not content, so `content_hash` and dedup behave as before and a flaky browser can never change what counts as a changed page. Cost: JS-injected text is absent from `text` while present in `blocks`; the demo pages are static.
7. **Failures degrade, with the existing reasons.** The closed reason set belongs to the `web-collection` spec; adding `render_failed` would be a MODIFIED requirement on that spec while `scraper-orchestration` is also editing run behaviour. This change maps render failures onto the existing set (`timeout`, `blocked`, `blocked_target`, `storage_error`, else `parse_error`) with a `render:` detail prefix. Alternative if the team prefers a dedicated reason: a one-line delta later (open question 5).
8. **Flag by environment, not by source.** `SCRAPER_RENDER_HOSTS` is env-only like all scraper config, needs no contract or migration, and is enough for two hosts. It also keeps `scraper-v2-sources` independent: it seeds rows and nothing else.
9. **Viewport names and sizes** follow the contract enum (`desktop`, `tablet`, `mobile`) and are constants in one module: 1440x900, 820x1180, 390x844 CSS pixels at device scale factor 1 (smaller PNGs).
10. **Hardening of the container**: non-root user, read-only root filesystem with a tmpfs for the browser's profile and `/tmp`, `no-new-privileges`, `cap_drop: [ALL]`, CPU and memory limits, `shm_size` for Chromium, fresh browser context per render, `Accept-Language: pl-PL`. Whether Chromium's sandbox works under these settings is checked in task 3.4; if it needs `--no-sandbox`, that is acceptable only because the container holds no secrets, sits on no internal network, and the decision is written into ADR 0105.

## Risks / Trade-offs

- **DNS rebinding between our check and Chromium's own resolution.** Playwright cannot pin the resolved address per request like our TLS client does. The request check reduces it; the container has no secrets and no `data` network. Residual risk recorded in ADR 0105.
- **Image size and build time** (browser download): a hardware-requirements line in the README, and the image builds only with the stack's render service. Mitigation: the browser build is pinned and checksum-verified, built once.
- **Layout heuristics are heuristics** (`legal`, `requires_interaction`, colour of images and gradients). Wrong guesses are made visible with tests on small synthetic pages per rule, and `null` is preferred to a guess.
- **Payload size**: three viewports of up to 600 blocks each is hundreds of KB in `documents.payload` (JSONB, TOASTed). Caps are env settings and `truncated` is reported; the effect on the API's `GET /findings/{id}` response is checked in the end-to-end task.
- **Time**: Playwright, Chromium and the confinement are the largest single piece of scraper work left. The first useful slice is a render of one demo page with blocks and three PNGs (groups 2 and 3); the compose service and wiring (groups 4 and 5) can follow if the clock is tight, and the visual rules then stay `not_applicable` as they are today.

## Open Questions

1. **Occlusion (contract, Damian).** R5 includes "przesłonięcie przez inne elementy", and `block` has no field for it. Proposed shape: optional `occluded: boolean | null` ("another element, such as a sticky bar, banner or overlay, covers the block's centre point"), measured with `document.elementFromPoint`. After Integration #1 this needs the whole team and a version bump (`IW_CONTRACT_CHANGE=1`); until then `region: overlay` is the only hint. Task 2.5 stays blocked on the answer; nothing else waits for it.
2. **Per-source switch.** Env host list now; a `render` field on `sources` later would need the contract, an Alembic revision and the dashboard's source form. Not proposed.
3. **`legal` word list.** The Polish and English words in the spec (`legal`, `disclaimer`, `zastrzezen`, `regulamin`, `przypis`) are a guess from the demo pages; Damian to add words R6 needs.
4. **Mobile emulation.** Resizing keeps desktop markup. Real mobile emulation (mobile User-Agent, touch, device scale) needs a new context per viewport and a second page load, i.e. three requests per document. Decide after seeing the demo pages.
5. **Render failure reason.** Reuse of the closed set (decision 7) or a new `render_failed` reason.
