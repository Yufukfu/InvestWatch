# Spec Delta

## Purpose
Give the visual M2 rules (R4-R8, R13) the layout they need, by rendering selected pages in a confined browser and attaching per-viewport screenshots and text blocks to the document, without ever losing the text document when rendering fails.

## ADDED Requirements

### Requirement: Render only the pages that need it
The scraper SHALL run the render step only for a source that is collectable, whose `source_kind` is `firm_own` and whose `target_modules` include `M2`, and only while `SCRAPER_RENDER_ENABLED` is true (default false) and the shared budget `SCRAPER_RENDER_MAX_PER_HOUR` (default 20 renders per UTC hour across all workers) is not spent. When the budget is spent the render SHALL be skipped without a job error and `scrape_meta.render.skipped` SHALL be `budget`. The render step SHALL run after the page was fetched and parsed, and SHALL NOT replace the document's `text`, `content_hash` or `scrape_meta.scraper`.

#### Scenario: Firm's own M2 page
- **WHEN** an active web source with `source_kind` `firm_own` and `target_modules` `["M2"]` is collected and `SCRAPER_RENDER_ENABLED` is true
- **THEN** the render step runs for it

#### Scenario: Third-party page targeting M2
- **WHEN** a source has `source_kind` `third_party` or `unknown`, even with `M2` in its `target_modules`
- **THEN** no render step runs and the document has no `blocks` and no `screenshots`

#### Scenario: Firm's own page without M2
- **WHEN** a `firm_own` source has `target_modules` `["M1"]`
- **THEN** no render step runs

#### Scenario: Kill switch
- **WHEN** `SCRAPER_RENDER_ENABLED` is false or unset
- **THEN** no browser is started for any source and every document is ingested as before

#### Scenario: Budget spent
- **WHEN** the hour's render budget is used up and another qualifying source is collected
- **THEN** the document is ingested without layout, `scrape_meta.render.skipped` is `budget` and no job error is recorded

#### Scenario: Text comes from the static parse
- **WHEN** a rendered page's browser DOM text differs from the static parse
- **THEN** the stored `text` and `content_hash` are the static parse's, so rerunning an unchanged page still deduplicates

### Requirement: Render goes through the same guards as fetch
Before the browser opens a page the scraper SHALL apply, in the same order and with the same shared state as `fetch`: the URL, port and address guard, `robots.txt`, the per-domain rate limit and `Retry-After` / failure pause, and the run's identity (User-Agent, client hints, `Accept-Language`) and proxy; the `mobile` viewport SHALL use a mobile variant of that identity of the same browser family and version that passes the same pairing check, and `desktop` and `tablet` SHALL use the run's identity. Each viewport is one navigation and SHALL pass the rate limit and the domain gate as its own request. A block signal in any viewport SHALL end the render, the viewports not yet loaded SHALL NOT be attempted, and nothing SHALL be retried in the same run. A `robots.txt` refusal SHALL skip rendering and is not a block.

#### Scenario: Refused by robots
- **WHEN** `robots.txt` disallows the page for the scraper's agent
- **THEN** the browser is not started and no screenshot or block is produced

#### Scenario: Domain paused
- **WHEN** the domain gate reports a pause (`Retry-After` or failure cooldown)
- **THEN** the render step is skipped and the pause is not shortened

#### Scenario: Block response
- **WHEN** the page answers 403 or 429, or the body carries a block marker
- **THEN** rendering stops, a job error with reason `blocked` is recorded and nothing is retried in this run

#### Scenario: Identity matches the run
- **WHEN** the run drew a Chrome-family identity
- **THEN** the `desktop` and `tablet` contexts use that User-Agent, client hints and `Accept-Language`, the `mobile` context uses an Android Chrome user agent of the same Chrome version with `sec-ch-ua-mobile` `?1`, and every context uses the proxy of the run without logging its credentials

#### Scenario: Mobile identity does not pair
- **WHEN** the mobile variant's user agent version differs from its client hints or from the pinned browser's major version
- **THEN** the pairing check rejects it before any request is made

#### Scenario: One navigation per viewport
- **WHEN** a page is rendered
- **THEN** the browser performs one navigation in each of three fresh contexts, each counted as a request against the domain's rate limit

#### Scenario: Block in the second viewport
- **WHEN** the `mobile` navigation answers 403 or 429
- **THEN** the render ends with reason `blocked`, the `tablet` navigation is not attempted and the document is still ingested

#### Scenario: Mobile emulation honours the viewport meta tag
- **WHEN** a page declares `<meta name="viewport" content="width=device-width">` and lays out differently at that width
- **THEN** the `mobile` blocks reflect the mobile layout, not the desktop markup scaled down

### Requirement: The browser is confined
Every request the browser makes SHALL be intercepted and checked. A request SHALL be aborted when its scheme is not http(s), its port is not in `ALLOWED_PORTS`, its host resolves to a non-public address, or its resource type is `media`, `websocket` or `eventsource`; a navigation to a host other than the source host (and its redirects within the same registrable domain) SHALL be aborted. Downloads, new pages, permission prompts and dialogs SHALL be refused. The browser process SHALL hold no database, Redis or object-storage credentials.

#### Scenario: Private address from the page
- **WHEN** the page's script or stylesheet references `http://169.254.169.254/` or a name that resolves to a private range
- **THEN** that request is aborted and the render continues

#### Scenario: Navigation away
- **WHEN** the page tries to navigate or redirect to another registrable domain, open a popup or start a download
- **THEN** it is refused and the original page is measured

#### Scenario: Third-party styles and fonts
- **WHEN** the page loads CSS, fonts and images from a public CDN host
- **THEN** they are allowed, so the layout matches what a visitor sees

#### Scenario: No secrets in the browser
- **WHEN** the renderer container is inspected
- **THEN** its environment has no `DATABASE_URL`, `REDIS_URL` or `MINIO_*` variable

### Requirement: Store one screenshot per viewport
The scraper SHALL capture a full-page PNG for each of `desktop` (1440x900), `tablet` (820x1180) and `mobile` (390x844) CSS pixels, capped at `RENDER_MAX_PAGE_HEIGHT` CSS pixels (default 12000) and `RENDER_MAX_PNG_BYTES` bytes per image, upload each to the bucket `iw-raw` at `shot/{document_id}/{viewport}.png`, and set `screenshots.{viewport}` to that key.

#### Scenario: Three screenshots
- **WHEN** a page is rendered successfully
- **THEN** `screenshots` holds the keys of three objects that exist in `iw-raw` and start with the PNG signature

#### Scenario: Very long page
- **WHEN** a page is taller than `RENDER_MAX_PAGE_HEIGHT`
- **THEN** the image is cut at the cap and `scrape_meta.render.truncated` is `true`

#### Scenario: One viewport fails
- **WHEN** capturing the `tablet` image fails but the other two succeed
- **THEN** `screenshots.tablet` is `null`, the other two keys are set and a job error is recorded

### Requirement: Describe the text blocks of each viewport
For each viewport the scraper SHALL emit `blocks` in the contract's `block` shape: one entry per rendered block of text (the nearest block-level element with its own text), in document order, with `viewport`, `text`, `tag`, `font_size_px`, `font_weight`, `color`, `background_color` (both `#rrggbb`), `bbox` `[x, y, width, height]` in CSS pixels relative to the page, `visible`, `in_viewport_on_load`, `requires_interaction`, `region` and `overflow_clipped`. Text of `script`, `style`, `noscript` and `template` elements SHALL NOT appear. The text SHALL be taken verbatim and never interpreted.

#### Scenario: Small risk text
- **WHEN** a page shows body text at 16 px and a risk warning at 10 px
- **THEN** the two blocks report `font_size_px` 16 and 10

#### Scenario: Colours are resolved
- **WHEN** text has a semi-transparent colour over a white parent
- **THEN** `color` is the composited `#rrggbb` and `background_color` is `#ffffff`

#### Scenario: Background that cannot be computed
- **WHEN** the nearest background is an image or gradient
- **THEN** `background_color` is `null` rather than a guess

#### Scenario: Same text, three viewports
- **WHEN** a warning is visible on desktop and clipped on mobile
- **THEN** it appears in `blocks` once per viewport and the mobile entry has `overflow_clipped` `true`

#### Scenario: Non-text elements
- **WHEN** a page contains a script that holds the string "ryzyko"
- **THEN** no block is emitted for it

### Requirement: Say where a block is and whether it can be seen
`visible` SHALL be `false` for a block hidden by `display`, `visibility`, `opacity` 0 or a zero-size box, and such text SHALL still be emitted so that hiding is detectable. `in_viewport_on_load` SHALL be `true` only when the block's box is inside the first viewport height without scrolling. `requires_interaction` SHALL be `true` for a block inside a closed `details`, or hidden and controlled by a visible element (`summary`, or an element whose `aria-controls` names it with `aria-expanded` `false`), and `false` otherwise. `region` SHALL be `footer` inside `footer` or `[role=contentinfo]`, `header` inside `header` or `[role=banner]`, `aside` inside `aside`, `overlay` inside a fixed or modal positioned layer, `legal` inside an element whose id, class or accessible name contains `legal`, `disclaimer`, `zastrzezen`, `regulamin` or `przypis` (case-insensitive, diacritics folded), and `main` otherwise.

#### Scenario: Collapsed accordion
- **WHEN** a risk text sits in a closed `details` element
- **THEN** its block has `requires_interaction` `true` and `visible` `false`

#### Scenario: Below the fold
- **WHEN** a block starts below the first viewport height
- **THEN** `in_viewport_on_load` is `false`

#### Scenario: Footer legal text
- **WHEN** a risk warning is inside `<footer><div class="legal">`
- **THEN** its `region` is `legal`

#### Scenario: Cookie banner
- **WHEN** a fixed-position banner contains text
- **THEN** that text's `region` is `overlay`

### Requirement: Bound the work
The renderer SHALL stop a render that exceeds `RENDER_TIMEOUT_SECONDS` (default 90, for all viewports together), SHALL emit at most `RENDER_MAX_BLOCKS` blocks per viewport (default 600) with each block's text cut at 4000 characters, and SHALL return at most `RENDER_MAX_PNG_BYTES` per image. When a cap is hit, `scrape_meta.render.truncated` SHALL be `true`. One render at a time per browser process SHALL be the default (`RENDER_CONCURRENCY`, default 1).

#### Scenario: Timeout
- **WHEN** the page never finishes loading within the timeout
- **THEN** the render ends with reason `timeout`, the browser context is closed and no process is left running

#### Scenario: Too many blocks
- **WHEN** a viewport has more blocks than `RENDER_MAX_BLOCKS`
- **THEN** the first `RENDER_MAX_BLOCKS` in document order are kept and `scrape_meta.render.truncated` is `true`

#### Scenario: Queue of renders
- **WHEN** two renders are requested at once with the default concurrency
- **THEN** the second waits for the first and neither fails

### Requirement: Rendering never costs the text document
When rendering fails for any reason (browser crash, timeout, block, refused target, renderer unreachable, malformed renderer response, upload failure) the scraper SHALL still ingest the document from the static parse without `blocks` and `screenshots`, and SHALL record one job error per failed render: `blocked` for a block signal, `blocked_target` for a refused target, `storage_error` for a failed upload, and `render_failed` for every other failure, with a detail that names the cause and contains no URL query, credentials or proxy. A render failure SHALL NOT trigger a queue retry or a domain failure cooldown.

#### Scenario: Browser crashes
- **WHEN** the browser process dies during the render
- **THEN** the document is inserted with no `blocks` and no `screenshots` and one job error with reason `render_failed` is recorded

#### Scenario: Render timeout
- **WHEN** the render exceeds `RENDER_TIMEOUT_SECONDS`
- **THEN** the job error reason is `render_failed` (not `timeout`), the document is inserted, the job is not retried and the domain gets no failure cooldown

#### Scenario: Renderer unreachable
- **WHEN** the renderer service does not answer
- **THEN** the document is still inserted and a `render_failed` job error is recorded; the next run tries again

#### Scenario: Visual rules stay honest
- **WHEN** a document has no `blocks`
- **THEN** its `blocks` is empty or absent, never a fabricated block

### Requirement: Store render output with the document and clean up
The scraper SHALL upload the screenshots before inserting the document row, like the raw HTML, and SHALL remove them when the insert certainly did not commit or the document turns out to be a duplicate. The inserted `blocks` and `screenshots` SHALL validate against the `ScrapedDocument` v1 schema, and `scrape_meta` SHALL carry `render` with the browser version and the `truncated` flag.

#### Scenario: Duplicate page
- **WHEN** a rendered page has the same `content_hash` as a stored document of the same source
- **THEN** no row is inserted and the uploaded screenshots are removed

#### Scenario: Insert fails
- **WHEN** the insert fails before the commit
- **THEN** the screenshot objects are removed

#### Scenario: Blocks reach analytics
- **WHEN** a rendered document is stored and announced
- **THEN** `documents.payload.blocks` is a non-empty array whose entries validate against the contract's `block` definition

### Requirement: Run the browser in an isolated container
The renderer SHALL be a separate image and service with a pinned Playwright version and a pinned, checksum-verified browser build, run as a non-root user with a read-only root filesystem, `no-new-privileges`, dropped capabilities and CPU and memory limits, attached only to the `egress` network and a private network shared with the scraper, and reachable from the scraper only. It SHALL keep no state between renders and SHALL use a fresh browser context, with no cookies carried over, for every viewport of every render.

#### Scenario: Not reachable from outside
- **WHEN** the stack is up
- **THEN** the renderer publishes no host port and is not on the `data` or `edge` networks

#### Scenario: Fresh context
- **WHEN** two viewports or two renders run one after the other
- **THEN** the second sees no cookies or storage from the first

#### Scenario: Image start-up check
- **WHEN** the renderer container starts
- **THEN** it launches the pinned browser once and reports its version on its health endpoint, or reports unhealthy
