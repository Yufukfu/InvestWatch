# Tasks

Each group from 2 on is one commit. Its first task is the failing test and its last is the mutation check (`iw-commit-cycle` step 3), completed as `mutations: N tried, N caught` (or `mutations: n/a, <reason>`). Groups 1 and 6 are agreements and docs only. Starts after `scraper-orchestration` is merged (group 5 hooks into its `run_source`); groups 1-4 only need `scraper-ingest` and can start on `main` now. Browser tests run in the renderer image's test target (Chromium is not installed locally). Fixtures are small synthetic pages, one per visual rule, plus saved real pages of the demo set in `tests/fixtures/`; the local fixture server passes the guards through the injected resolver, as in the fetch tests.

## 1. Agreements and ADR

- [ ] 1.1 Measure with evidence: build a throwaway image with the pinned Playwright, Chromium and its system libraries; record size, browser version and checksum source, and whether Chromium's sandbox starts as a non-root user with `cap_drop: [ALL]`, `no-new-privileges` and a read-only root filesystem. Write ADR 0105 (renderer as a separate image and service, options A/B/C of design decision 1, hardening, the DNS-rebinding residual risk) and list it in `.docs/decisions/README.md`; docs-check clean
- [ ] 1.2 Ask Damian (contract question, not a change): `occluded` on `block` (design open question 1) and the `legal` word list (open question 3); record his answer in `design.md`. Task 2.5 is blocked until then

## 2. Measuring a page in the browser

- [ ] 2.1 Failing tests on synthetic pages, then the in-page measurement script and its Python wrapper: block selection (nearest block-level element with its own text, no `script`, `style`, `noscript`, `template`), `font_size_px`, `font_weight`, `bbox`, document order; the small-risk-text and non-text scenarios pass
- [ ] 2.2 Failing tests, then colour resolution (alpha compositing over the nearest opaque ancestor, `null` for image or gradient backgrounds, `#rrggbb` only); the colour scenarios pass
- [ ] 2.3 Failing tests, then `visible`, `in_viewport_on_load`, `requires_interaction` (closed `details`, `aria-controls` with `aria-expanded=false`) and `region` (footer, header, aside, overlay, legal word list with diacritics folded); the collapsed-accordion, below-the-fold, footer-legal and cookie-banner scenarios pass
- [ ] 2.4 Failing tests, then the three viewports by resizing one page and `overflow_clipped`; the same-text-three-viewports scenario passes and every emitted block validates against the contract's `block` definition (`contracts/validate.py`)
- [ ] 2.5 BLOCKED on 1.2: if the team accepts `occluded`, failing test with a sticky bar over a risk text, then `document.elementFromPoint`; only with `IW_CONTRACT_CHANGE=1` after the whole team agrees. If refused, close this task as not done
- [ ] 2.6 Mutation check; line reads `mutations: N tried, N caught`

## 3. A confined, bounded render

- [ ] 3.1 Failing tests, then request interception: abort non-http(s), ports outside `ALLOWED_PORTS`, private or metadata addresses, `media`, `websocket` and `eventsource`; cross-domain navigation, popups, downloads, dialogs and permission prompts refused; third-party CSS, fonts and images allowed. The private-address, navigation-away and third-party-styles scenarios pass (reusing `iw_scraper.targets`)
- [ ] 3.2 Failing tests, then screenshots per viewport with `RENDER_MAX_PAGE_HEIGHT` and `RENDER_MAX_PNG_BYTES`, and one failing viewport yielding null with the others kept; the three-screenshots, long-page and one-viewport-fails scenarios pass (PNG signature checked)
- [ ] 3.3 Failing tests, then `RENDER_TIMEOUT_SECONDS`, `RENDER_MAX_BLOCKS`, 4000-character block text cap, `scrape_meta.render.truncated`, a fresh browser context per render and `RENDER_CONCURRENCY`; the timeout, too-many-blocks, queue and fresh-context scenarios pass and no browser process outlives a timed-out render
- [ ] 3.4 Failing test, then the identity and proxy of the run applied to the context (User-Agent, client hints, `Accept-Language`, proxy never logged or placed in an error detail) and the block outcome (403, 429 or block marker ends the render with `blocked`); the identity and block scenarios pass. Applies the sandbox finding of 1.1
- [ ] 3.5 Mutation check; line reads `mutations: N tried, N caught`

## 4. Renderer service and container

- [ ] 4.1 Failing tests, then the HTTP service (`POST /render` with target, source host, ports, identity, proxy; JSON with blocks, base64 PNGs and render meta; `GET /health` with the browser version or 503); request validation, size limits, no query or credential in logs; the start-up-check scenario passes
- [ ] 4.2 Failing tests, then the Dockerfile target and compose service: pinned Playwright and checksum-verified browser, non-root, read-only root filesystem with tmpfs, `no-new-privileges`, `cap_drop`, limits, `shm_size`, networks `egress` and a private `render` network shared with the scraper, no host port, no `DATABASE_URL`, `REDIS_URL` or `MINIO_*`; the not-reachable and no-secrets scenarios pass (checked with `docker compose config` and `docker inspect`)
- [ ] 4.3 Mutation check; `mutations: n/a, container wiring only` unless service code changed in 4.2 (then N tried, N caught)

## 5. Wiring: the run and the ingest

- [ ] 5.1 Failing tests, then `SCRAPER_RENDER_HOSTS` in the settings and the render client (call the renderer after the robots, rate-limit and domain-gate checks, one load per run, shared gate state); the listed-host, M2-only, unlisted-host, robots-refusal and domain-paused scenarios pass over a stub renderer
- [ ] 5.2 Failing tests, then the hook in `run_source` (render after parse, result in `page["render"]`, `text`, `content_hash` and `scrape_meta.scraper` unchanged); the text-comes-from-static-parse scenario passes
- [ ] 5.3 Failing tests, then ingest of render output: upload PNGs to `shot/{document_id}/{viewport}.png` before the insert, set `screenshots` and `blocks`, `scrape_meta.render`, schema validation, and removal on duplicate or certainly-uncommitted insert; the duplicate, insert-fails and blocks-reach-analytics scenarios pass against real PostgreSQL and MinIO
- [ ] 5.4 Failing tests, then failure degradation (browser crash, timeout, block, renderer unreachable, upload failure): the document is inserted without `blocks` and `screenshots`, reasons mapped per the spec, detail prefixed `render:` and free of query, credentials and proxy; the crash, unreachable and visual-rules-stay-honest scenarios pass
- [ ] 5.5 Mutation check; line reads `mutations: N tried, N caught`

## 6. End to end and closing

- [ ] 6.1 Failing end-to-end check on docker compose, saved XTB and mBank IKE pages behind a local stub server and one worker with the render service: a seeded M2 source yields a document whose `payload.blocks` is non-empty and schema-valid for three viewports, three PNGs in `iw-raw`, and `GET /api/documents/{id}/screenshot/desktop` returns an image if `api` is up; a rerun adds nothing and leaves no extra object. Fix only what this shows; paste the output in the PR body
- [ ] 6.2 Measure the payload: size of `documents.payload` for the demo pages and of `GET /api/findings/{id}`; if the response is too large for the dashboard, report to Kacper and Damian with numbers (no change here)
- [ ] 6.3 Apply the `iw-docs-update` skill (`scraper/CLAUDE.md`, `scraper/README.md` settings and the hardware note, `iw-scraper-conventions` render rung, `.docs/analytics-plan.md` §5 note on `blocks`, `.docs/integration-plan.md` if the key or meta shape differs, ADR 0105 listed, your own row in `.docs/status/scraper.md`), run docs-check, run `pip-audit` on the scraper and renderer requirements and record it in `.docs/security-audit.md`, and add the `iw-ai-log` row
- [ ] 6.4 Run the `iw-pr-review` skill and fix real findings; `iw-reviewer` reports no open blocking findings

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
