# Spec Delta

## Purpose
Give the visual M2 rules (R4-R8, R13) the layout they need, by rendering selected pages in a confined browser and attaching per-viewport screenshots and text blocks to the document, without ever losing the text document when rendering fails.

## ADDED Requirements

### Requirement: Render only the pages that need it
The scraper SHALL run the render step only for a collectable `firm_own` source whose `target_modules` include `M2`, only while `SCRAPER_RENDER_ENABLED` is true (default false), and only while the shared budget `SCRAPER_RENDER_MAX_PER_HOUR` (default 20 renders per UTC hour across all workers) is not spent.

#### Scenario: Budget, order and what the render leaves alone
- **WHEN** the render step is considered for a document
- **THEN** when the budget is spent the render SHALL be skipped without a job error and `scrape_meta.render.skipped` SHALL be `budget`
- **AND** the render step SHALL run after the page was fetched and parsed and after the duplicate check, so a page whose `content_hash` is already stored costs neither a browser nor budget
- **AND** the render step SHALL NOT replace the document's `text`, `content_hash` or `scrape_meta.scraper`

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

#### Scenario: Unchanged page costs nothing
- **WHEN** a page with the same `content_hash` as a stored document of the source is collected
- **THEN** no renderer call is made and the hour's budget is unchanged

#### Scenario: Text comes from the static parse
- **WHEN** a rendered page's browser DOM text differs from the static parse
- **THEN** the stored `text` and `content_hash` are the static parse's, so rerunning an unchanged page still deduplicates

### Requirement: Render goes through the same guards as fetch
The scraper SHALL call the renderer once per viewport, in the order `desktop`, `mobile`, `tablet`, and before each call SHALL apply the shared state `fetch` uses: the per-domain rate limit, the `Retry-After` and failure pause, and the run's identity and proxy.

#### Scenario: What each call carries and when the render ends
- **WHEN** the renderer is called for a viewport
- **THEN** the URL, port and address guard and `robots.txt` were applied by the run before the page was fetched, and the renderer SHALL re-check the address of every browser request
- **AND** the `mobile` viewport SHALL use a mobile variant of the run's identity of the same browser family and version that passes the same pairing check, and `desktop` and `tablet` SHALL use the run's identity
- **AND** each viewport is one navigation and SHALL pass the rate limit and the domain gate as its own request
- **AND** a block signal in any viewport SHALL end the render, the viewports not yet loaded SHALL NOT be attempted, a `Retry-After` it carries SHALL be recorded in the domain gate, and nothing SHALL be retried in the same run

#### Scenario: Refused by robots
- **WHEN** `robots.txt` disallows the page for the scraper's agent
- **THEN** the run ends before the fetch as it does today, the browser is not started and no screenshot or block is produced

#### Scenario: Domain paused
- **WHEN** the domain gate reports a pause (`Retry-After` or failure cooldown)
- **THEN** the render step is skipped with `scrape_meta.render.skipped` `paused`, no job error is recorded and the pause is not shortened

#### Scenario: Block response
- **WHEN** the page answers 403 or 429, or the body carries a block marker
- **THEN** rendering stops, a job error with reason `blocked` is recorded, a `Retry-After` header is passed to the domain gate and nothing is retried in this run

#### Scenario: Identity matches the run
- **WHEN** the run drew a Chrome-family identity
- **THEN** the `desktop` and `tablet` contexts use that User-Agent, client hints and `Accept-Language`, the `mobile` context uses an Android Chrome user agent of the same Chrome version with `sec-ch-ua-mobile` `?1`, and every context uses the proxy of the run without logging its credentials

#### Scenario: Mobile identity does not pair
- **WHEN** the mobile variant's user agent version differs from its client hints or TLS profile
- **THEN** the pairing check rejects it (the test suite runs the check on the variant of every table entry)

#### Scenario: Identity is adapted to the browser
- **WHEN** a request names a Chrome major that differs from the renderer's browser (the pinned Chromium has no build for `CHROME_VERSION`, ADR 0107)
- **THEN** the renderer sends a user agent and client hints with the browser's own major and keeps the platform, mobile flag and `Accept-Language` of the request

#### Scenario: Identity is not Chrome
- **WHEN** a request carries a user agent that is not Chrome
- **THEN** the renderer refuses it before any navigation and the render ends with `render_failed`

#### Scenario: One navigation per viewport
- **WHEN** a page is rendered
- **THEN** the scraper makes three renderer calls in the order `desktop`, `mobile`, `tablet`, each preceded by the domain's rate-limit turn, and the browser performs one navigation in a fresh context for each

#### Scenario: Block in the second viewport
- **WHEN** the `mobile` navigation answers 403 or 429
- **THEN** the render ends with reason `blocked`, the `tablet` navigation is not attempted and the document is still ingested

#### Scenario: Mobile emulation honours the viewport meta tag
- **WHEN** a page declares `<meta name="viewport" content="width=device-width">` and lays out differently at that width
- **THEN** the `mobile` blocks reflect the mobile layout, not the desktop markup scaled down

### Requirement: The browser is confined
Every request the browser makes SHALL be intercepted and checked, and a request SHALL be aborted when its scheme is not http(s), its port is not in `ALLOWED_PORTS`, its host resolves to a non-public address, its resource type is `media` or `eventsource`, or it is a websocket.

#### Scenario: Navigations, redirects and refused features
- **WHEN** the browser navigates, follows a redirect or the page uses a browser feature
- **THEN** a navigation to a host other than the source host's site SHALL be refused without replacing the page
- **AND** because Chromium follows redirects without asking the interceptor (measured, ADR 0107), every redirect hop of every request the browser makes (the first navigation, subresources, fetches and frames) SHALL be checked after the load against the same address and port rules, a navigation hop also against the source site
- **AND** a render with a hop that left the site, reached a non-public address or a closed port SHALL fail and keep nothing of the page it landed on
- **AND** downloads, new pages, service workers, shared workers, permission prompts and dialogs SHALL be refused
- **AND** the browser process SHALL hold no database, Redis or object-storage credentials

#### Scenario: Private address from the page
- **WHEN** the page's script or stylesheet references `http://169.254.169.254/` or a name that resolves to a private range
- **THEN** that request is aborted and the render continues

#### Scenario: Navigation away
- **WHEN** the page tries to navigate or redirect to another registrable domain, open a popup or start a download
- **THEN** it is refused and the original page is measured

#### Scenario: Redirect away
- **WHEN** the first navigation is redirected to another registrable domain
- **THEN** the render fails with `render_failed`, and no screenshot or block of the page it landed on is produced

#### Scenario: Redirect of a subresource
- **WHEN** an image, stylesheet, fetch or iframe of the page is redirected to a non-public address or a port outside `ALLOWED_PORTS`, at any hop of its chain
- **THEN** the render fails with `blocked_target` and no screenshot or block is produced, and a redirect between public hosts is followed

#### Scenario: Third-party styles and fonts
- **WHEN** the page loads CSS, fonts and images from a public CDN host
- **THEN** they are allowed, so the layout matches what a visitor sees

#### Scenario: No secrets in the browser
- **WHEN** the renderer container is inspected
- **THEN** its environment has no `DATABASE_URL`, `REDIS_URL` or `MINIO_*` variable

### Requirement: Store one screenshot per viewport
The scraper SHALL capture a full-page PNG for each of `desktop` (1440x900), `tablet` (820x1180) and `mobile` (390x844) CSS pixels, capped at `RENDER_MAX_PAGE_HEIGHT` CSS pixels (default 12000) and `RENDER_MAX_PNG_BYTES` bytes per image (default 8000000; a larger image is shortened until it fits, and a page that does not fit even one viewport height fails that viewport), upload each to the bucket `iw-raw` at `shot/{document_id}/{viewport}.png`, and set `screenshots.{viewport}` to that key.

#### Scenario: Three screenshots
- **WHEN** a page is rendered successfully
- **THEN** `screenshots` holds the keys of three objects that exist in `iw-raw` and start with the PNG signature

#### Scenario: Very long page
- **WHEN** a page is taller than `RENDER_MAX_PAGE_HEIGHT`
- **THEN** the image is cut at the cap and `scrape_meta.render.truncated` is `true`

#### Scenario: One viewport fails
- **WHEN** capturing the `tablet` image fails but the other two succeed
- **THEN** `screenshots.tablet` is `null`, the other two keys are set and a job error is recorded

#### Scenario: Failure after the first viewport
- **WHEN** a renderer call other than a block or a refused target fails after an earlier one succeeded (a spent render deadline or a pause between calls is not a call and still discards the render)
- **THEN** the viewports already taken and their blocks are stored, the failed and the not attempted viewports are `null`, and one job error is recorded

#### Scenario: Block or refusal after the first viewport
- **WHEN** a later viewport is blocked or its target is refused after an earlier one succeeded
- **THEN** no screenshot and no block is stored and one job error with reason `blocked` or `blocked_target` is recorded

### Requirement: Describe the text blocks of each viewport
For each viewport the scraper SHALL emit `blocks` in the contract's `block` shape: one entry per rendered block of text (the nearest block-level element with its own text), in document order, taken verbatim and never interpreted.

#### Scenario: Fields of a block
- **WHEN** a viewport is measured
- **THEN** each block SHALL carry `viewport`, `text`, `tag`, `font_size_px`, `font_weight` (an integer, rounded), `color`, `background_color` (both `#rrggbb`), `bbox` `[x, y, width, height]` in CSS pixels relative to the page, `visible`, `in_viewport_on_load`, `requires_interaction`, `region` and `overflow_clipped`
- **AND** text of `script`, `style`, `noscript` and `template` elements SHALL NOT appear

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
`visible`, `in_viewport_on_load`, `requires_interaction` and `region` SHALL say where a block is and whether it can be seen, and `region` SHALL always be set, never `null` (analytics' R6 cannot pass a block with unknown region).

#### Scenario: Visibility and interaction flags
- **WHEN** a block is measured
- **THEN** `visible` SHALL be `false` for a block hidden by `display`, `visibility`, `opacity` 0 or a zero-size box, and such text SHALL still be emitted so that hiding is detectable
- **AND** `in_viewport_on_load` SHALL be `true` only when the block's box is inside the first viewport height without scrolling
- **AND** `requires_interaction` SHALL be `true` for a block inside a closed `details`, or hidden and controlled by a visible element (`summary`, or an element whose `aria-controls` names it with `aria-expanded` `false`), and `false` otherwise

#### Scenario: Region values
- **WHEN** a block's `region` is decided
- **THEN** `region` SHALL be `footer` inside `footer` or `[role=contentinfo]`, `header` inside `header` or `[role=banner]`, `aside` inside `aside`, and `overlay` inside a fixed or modal positioned layer
- **AND** `region` SHALL be `legal` inside an element whose id, class, accessible name or section heading contains one of the placement words in one list (case-insensitive substring, diacritics folded): `legal`, `prawn`, `klauzul`, `objasnien`, `warunk`, `regulacj`, `regulamin`, `zastrzezen`, `przypis`, `knf`, `disclaimer`, `disclosure`, `footnote`, `endnote`, `fine-print`, `fineprint`, `small-print`, `important-information`, `important-notice`, `terms`, `tnc`, `notice`, `compliance`, `regulatory`, `imprint`, `impressum`
- **AND** `region` SHALL also be `legal` inside `small`, `role=note`, `role=doc-footnote` or `role=doc-endnotes`, and `main` otherwise

#### Scenario: The legal list holds placement words only
- **WHEN** the list of placement words is maintained
- **THEN** it SHALL hold placement words only, never content words such as `risk`, `ryzyk`, `ostrzezen` or `warning`: a prominent risk box below the fold is not legal text and must not fail R6 as one

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

#### Scenario: Placement words, not content words
- **WHEN** a below-the-fold `<div class="risk-warning">` and a `<div class="nota-prawna">` each hold text
- **THEN** the first block's `region` is `main` and the second's is `legal`

#### Scenario: Region is never null
- **WHEN** a block matches no region rule
- **THEN** its `region` is `main`

### Requirement: Bound the work
The renderer SHALL stop a render that exceeds `RENDER_TIMEOUT_SECONDS` (default 90, for all viewports together; the scraper passes each call the time left), SHALL emit at most `RENDER_MAX_BLOCKS` blocks per viewport (default 600) with each block's text cut at 4000 characters, and SHALL return at most `RENDER_MAX_PNG_BYTES` per image. When a cap is hit, `scrape_meta.render.truncated` SHALL be `true`. One render at a time per browser process SHALL be the default (`RENDER_CONCURRENCY`, default 1).

#### Scenario: Timeout
- **WHEN** the page never finishes loading within the timeout
- **THEN** the render ends with reason `render_failed` (never `timeout`: the queue retries that), the browser context is closed and no process is left running

#### Scenario: Too many blocks
- **WHEN** a viewport has more blocks than `RENDER_MAX_BLOCKS`
- **THEN** the first `RENDER_MAX_BLOCKS` in document order are kept and `scrape_meta.render.truncated` is `true`

#### Scenario: Attempt timeout shorter than the render
- **WHEN** `SCRAPER_RENDER_ENABLED` is true and `SCRAPER_ATTEMPT_TIMEOUT` is less than `RENDER_TIMEOUT_SECONDS` plus 60 seconds
- **THEN** the scraper refuses to start with a message naming both settings, so a render cannot be cut off by the job's attempt timeout

#### Scenario: Queue of renders
- **WHEN** two renders are requested at once with the default concurrency
- **THEN** the second waits for the first and neither fails

### Requirement: Rendering never costs the text document
When rendering fails for any reason the scraper SHALL still ingest the document from the static parse and SHALL record one job error per failed render, with a detail that names the cause and contains no URL query, credentials or proxy. A render failure SHALL NOT trigger a queue retry or a domain failure cooldown.

#### Scenario: Reasons and what is dropped
- **WHEN** the render fails by browser crash, timeout, block, refused target, renderer unreachable, malformed renderer response or upload failure
- **THEN** the document SHALL be ingested without `blocks` and `screenshots`, except that viewports already taken stay when a later renderer call fails (scenario "Failure after the first viewport")
- **AND** the job error reason SHALL be `blocked` for a block signal, `blocked_target` for a refused target, `storage_error` for a failed upload, and `render_failed` for every other failure

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
The renderer SHALL be a separate image and service with a pinned Playwright version and a browser build pinned by that version and the base image tag, run as a non-root user with a read-only root filesystem, `no-new-privileges`, dropped capabilities and CPU and memory limits, published to no host port.

#### Scenario: Pinning, networks, environment and state
- **WHEN** the renderer service is built and started
- **THEN** the browser build SHALL also be pinned by the checksum where the vendor publishes one
- **AND** the service SHALL be attached only to the `egress` network and an internal network `render` shared with the scraper
- **AND** it SHALL be started with an explicit `environment` and no `env_file`
- **AND** it SHALL keep no state between renders and SHALL use a fresh browser context, with no cookies carried over, for every viewport of every render

#### Scenario: Not reachable from outside
- **WHEN** the stack is up
- **THEN** the renderer publishes no host port and is not on the `data` or `edge` networks, and the `render` network is internal

#### Scenario: Fresh context
- **WHEN** two viewports or two renders run one after the other
- **THEN** the second sees no cookies or storage from the first

#### Scenario: Image start-up check
- **WHEN** the renderer container starts
- **THEN** it launches the pinned browser once and reports its version on its health endpoint, or reports unhealthy
