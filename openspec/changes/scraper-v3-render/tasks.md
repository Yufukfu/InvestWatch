# Tasks

Each group from 2 on is one commit. Its first task is the failing test and its last is the mutation check (`iw-commit-cycle` step 3), completed as `mutations: N tried, N caught` (or `mutations: n/a, <reason>`). Groups 1 and 7 are agreements and docs only. The groups follow the order of delivery (design decision 10): after group 4 the stack has real desktop and mobile screenshots, group 5 adds `blocks`, group 6 (tablet) is the first thing to drop if the clock is tight. Starts after `scraper-orchestration` is merged (group 4 hooks into its `run_source`); groups 1-3 only need `scraper-ingest` and can start on `main` now. Browser tests run in the renderer image's test target (Chromium is not installed locally). Fixtures are small synthetic pages, one per visual rule, plus saved real pages of the demo set in `tests/fixtures/`; the local fixture server passes the guards through the injected resolver, as in the fetch tests.

## 1. Agreements and ADR

- [ ] 1.1 Measure with evidence: build a throwaway image with the pinned Playwright, Chromium and its system libraries; record size, browser version (its major against `CHROME_VERSION`, design decision 4), checksum source, and whether Chromium's sandbox starts as a non-root user with `cap_drop: [ALL]`, `no-new-privileges` and a read-only root filesystem. Write ADR 0105 (renderer as a separate image and service, options A/B/C of design decision 1, hardening, the DNS-rebinding residual risk, three navigations per document) and list it in `.docs/decisions/README.md`; docs-check clean
- [ ] 1.2 Send Damian the two questions that are not blocking: the `legal` word list (design open question 2) and, for later, `occluded` (open question 1); record any answer in `design.md`. Nothing in groups 2-7 waits for the reply

## 2. A confined, bounded render with screenshots (desktop and mobile)

- [ ] 2.1 Failing tests, then `Reason.RENDER_FAILED` in `types.py` and `mobile_variant(identity)` in `identities.py` (Android Chrome of the same `CHROME_VERSION`, `sec-ch-ua-mobile: ?1`) accepted by `check_pairing`; the render-failure-reason and mobile-identity-does-not-pair scenarios pass, including that a mismatched variant is rejected before any request
- [ ] 2.2 Failing tests, then request interception: abort non-http(s), ports outside `ALLOWED_PORTS`, private or metadata addresses, `media`, `websocket` and `eventsource`; cross-domain navigation, popups, downloads, dialogs and permission prompts refused; third-party CSS, fonts and images allowed. The private-address, navigation-away and third-party-styles scenarios pass (reusing `iw_scraper.targets`)
- [ ] 2.3 Failing tests, then one fresh context per viewport with `viewport`, `has_touch`, `is_mobile` and the identity of the viewport (the run's for `desktop`, the mobile variant for `mobile`; the proxy applied, never logged or placed in an error detail), one navigation each, block outcome (403, 429 or block marker ends the render with `blocked`, later viewports not attempted); the identity, one-navigation-per-viewport, block-in-the-second-viewport and mobile-emulation scenarios pass. Applies the sandbox finding of 1.1
- [ ] 2.4 Failing tests, then screenshots per viewport with `RENDER_MAX_PAGE_HEIGHT` and `RENDER_MAX_PNG_BYTES`, one failing viewport yielding null with the others kept, `RENDER_TIMEOUT_SECONDS` for the whole render (no browser process outlives a timed-out render) and `RENDER_CONCURRENCY`; the three-screenshots (here two), long-page, one-viewport-fails, timeout and queue scenarios pass (PNG signature checked)
- [ ] 2.5 Mutation check; line reads `mutations: N tried, N caught`

## 3. Renderer service and container

- [ ] 3.1 Failing tests, then the HTTP service (`POST /render` with target, source host, ports, identity, mobile identity, proxy, viewports; JSON with blocks, base64 PNGs and render meta; `GET /health` with the browser version or 503); request validation, size limits, no query or credential in logs; the start-up-check scenario passes
- [ ] 3.2 Failing tests, then the Dockerfile target and compose service: pinned Playwright and checksum-verified browser, non-root, read-only root filesystem with tmpfs, `no-new-privileges`, `cap_drop`, limits, `shm_size`, networks `egress` and a private `render` network shared with the scraper, no host port, no `DATABASE_URL`, `REDIS_URL` or `MINIO_*`; the not-reachable and no-secrets scenarios pass (checked with `docker compose config` and `docker inspect`)
- [ ] 3.3 Mutation check; `mutations: n/a, container wiring only` unless service code changed in 3.2 (then N tried, N caught)

## 4. Wiring: the run and the ingest (screenshots reach the stack)

- [ ] 4.1 Failing tests, then `SCRAPER_RENDER_ENABLED`, `SCRAPER_RENDER_MAX_PER_HOUR` (Redis counter keyed by the UTC hour, shared by workers) and `RENDERER_URL` in the settings, and the render client (call the renderer after the robots, rate-limit and domain-gate checks, each viewport as its own request with shared gate state); the firm-own-M2, third-party-M2, firm-own-without-M2, kill-switch, budget-spent, robots-refusal and domain-paused scenarios pass over a stub renderer
- [ ] 4.2 Failing tests, then the hook in `run_source` (render after parse, result in `page["render"]`, `text`, `content_hash` and `scrape_meta.scraper` unchanged); the text-comes-from-static-parse scenario passes
- [ ] 4.3 Failing tests, then ingest of render output: upload PNGs to `shot/{document_id}/{viewport}.png` before the insert, set `screenshots`, `scrape_meta.render` (browser version, `truncated`, `skipped`), schema validation, and removal on duplicate or certainly-uncommitted insert; the duplicate and insert-fails scenarios pass against real PostgreSQL and MinIO
- [ ] 4.4 Failing tests, then failure degradation (browser crash, timeout, block, renderer unreachable, upload failure): the document is inserted without `blocks` and `screenshots`, one job error per failed render with `blocked`, `blocked_target`, `storage_error` or `render_failed`, detail free of query, credentials and proxy, and no queue retry or domain cooldown from a render failure; the crash, render-timeout, unreachable and visual-rules-stay-honest scenarios pass
- [ ] 4.5 Mutation check; line reads `mutations: N tried, N caught`

## 5. Blocks for R4-R8 and R13 (desktop and mobile)

- [ ] 5.1 Failing tests on synthetic pages, then the in-page measurement script and its Python wrapper: block selection (nearest block-level element with its own text, no `script`, `style`, `noscript`, `template`), `font_size_px`, `font_weight`, `bbox`, document order, caps (`RENDER_MAX_BLOCKS`, 4000-character text, `truncated`); the small-risk-text, non-text-elements and too-many-blocks scenarios pass
- [ ] 5.2 Failing tests, then colour resolution (alpha compositing over the nearest opaque ancestor, `null` for image or gradient backgrounds, `#rrggbb` only); the colour scenarios pass
- [ ] 5.3 Failing tests, then `visible`, `in_viewport_on_load`, `requires_interaction` (closed `details`, `aria-controls` with `aria-expanded=false`) and `region` (footer, header, aside, overlay, legal word list with diacritics folded); the collapsed-accordion, below-the-fold, footer-legal and cookie-banner scenarios pass
- [ ] 5.4 Failing tests, then `overflow_clipped` and the same text measured per viewport; the same-text-per-viewport scenario passes and every emitted block validates against the contract's `block` definition (`contracts/validate.py`)
- [ ] 5.5 Failing tests, then ingest sets `blocks` on the document and the blocks-reach-analytics scenario passes against real PostgreSQL and MinIO
- [ ] 5.6 Mutation check; line reads `mutations: N tried, N caught`

## 6. Tablet viewport (first to drop if time is short)

- [ ] 6.1 Failing tests, then the `tablet` context (820x1180, `has_touch`, the run's identity), its screenshot at `shot/{document_id}/tablet.png` and its blocks; the three-screenshots scenario passes with all three keys set
- [ ] 6.2 Mutation check; line reads `mutations: N tried, N caught`

## 7. End to end and closing

- [ ] 7.1 Failing end-to-end check on docker compose, saved XTB and mBank IKE pages behind a local stub server and one worker with the render service: a seeded `firm_own` + `M2` source yields a document whose `payload.blocks` is non-empty and schema-valid for the rendered viewports, PNGs in `iw-raw`, and `GET /api/documents/{id}/screenshot/desktop` returns an image if `api` is up; a rerun adds nothing and leaves no extra object. Fix only what this shows; paste the output in the PR body
- [ ] 7.2 Measure the payload: size of `documents.payload` for the demo pages and of `GET /api/findings/{id}`; if the response is too large for the dashboard, report to Kacper and Damian with numbers (no change here)
- [ ] 7.3 Apply the `iw-docs-update` skill (`scraper/CLAUDE.md`, `scraper/README.md` settings and the hardware note, `iw-scraper-conventions` render rung and the mobile identity, `.docs/analytics-plan.md` §5 note on `blocks`, `.docs/integration-plan.md` if the key or meta shape differs, ADR 0105 listed, your own row in `.docs/status/scraper.md`), run docs-check, run `pip-audit` on the scraper and renderer requirements and record it in `.docs/security-audit.md`, and add the `iw-ai-log` row
- [ ] 7.4 Run the `iw-pr-review` skill and fix real findings; `iw-reviewer` reports no open blocking findings

## Deferred follow-up (not part of this change's done criteria)

- `occluded` on `block` (design open question 1): only if the whole team accepts the contract change after Integration #1 (`IW_CONTRACT_CHANGE=1`); then a failing test with a sticky bar over a risk text and a `document.elementFromPoint` measurement, as its own small change. Nothing in groups 1-7 depends on it.
- `sources.config` column for per-source render and parser options: a proposal for Damian after the hackathon.

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
