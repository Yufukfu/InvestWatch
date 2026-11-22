# Tasks

Each group from 2 on is one commit. Its first task is the failing test and its last is the mutation check (`iw-commit-cycle` step 3), completed as `mutations: N tried, N caught` (or `mutations: n/a, <reason>`). Groups 1 and 7 are agreements and docs only. The groups follow the order of delivery (design decision 10): after group 4 the stack has real desktop and mobile screenshots, group 5 adds `blocks`, group 6 (tablet) is the first thing to drop if the clock is tight. Starts after `scraper-orchestration` is merged (group 4 hooks into its `run_source`); groups 1-3 only need `scraper-ingest` and can start on `main` now. Browser tests run in the renderer image's test target (Chromium is not installed locally; task 2.1 creates it). The renderer code lives in `scraper/src/iw_renderer/`. Fixtures are small synthetic pages, one per visual rule, plus saved real pages of the demo set in `tests/fixtures/`; the local fixture server passes the guards through the injected resolver, as in the fetch tests.

## 1. Agreements and ADR

- [x] 1.1 Measure with evidence: build a throwaway image with the pinned Playwright, Chromium and its system libraries; record size, browser version (its major against `CHROME_VERSION`, design decision 4), checksum source, and whether Chromium's sandbox starts as a non-root user with `cap_drop: [ALL]`, `no-new-privileges` and a read-only root filesystem. Write ADR 0107 (renderer as a separate image and service, options A/B/C of design decision 1, hardening, the DNS-rebinding residual risk, three navigations per document) and list it in `.docs/decisions/README.md`; docs-check clean
- [x] 1.2 Damian answered both questions in issue #34 (2026-11-21): the `legal` word list and `region` never null are folded into the spec and design; `occluded` stays deferred, as a nullable boolean in v2. Nothing in groups 2-7 waits

## 2. A confined, bounded render with screenshots (desktop and mobile)

- [x] 2.1 Renderer image test target first (Dockerfile target with the pinned Playwright and browser of task 1.1, the `iw_renderer` package skeleton, `pytest` inside it), so groups 2 and 5 can run browser tests; then failing tests and `Reason.RENDER_FAILED` in `types.py` (update `EXPECTED_REASONS` in `tests/test_types.py`) and `mobile_variant(identity)` in `identities.py` (Android Chrome of the same `CHROME_VERSION`, `sec-ch-ua-mobile: ?1`, `check_pairing`-checked for every table entry by the test suite); the render-failure-reason, mobile-identity-does-not-pair, identity-is-adapted-to-the-browser and identity-is-not-chrome scenarios pass (`iw_renderer/identity.py` rewrites the Chrome major to the browser's, per ADR 0107; `mobile_variant` takes an optional version)
- [x] 2.2 Failing tests, then request interception: abort non-http(s), ports outside `ALLOWED_PORTS`, private or metadata addresses, `media`, `eventsource` and websockets (`route_web_socket`); service workers blocked; cross-domain navigation, popups, downloads, dialogs and permission prompts refused; third-party CSS, fonts and images allowed. The private-address, navigation-away and third-party-styles scenarios pass. First move the pure address checks out of `targets.py` into a module free of `fetch`/`noble_tls`, re-exported from `targets` (design decision 3); `UrlGuard`'s host list is not used
- [x] 2.3 Failing tests, then one fresh context per viewport with `viewport`, `has_touch`, `is_mobile` and the identity of the viewport (the run's for `desktop`, the mobile variant for `mobile`; the proxy applied, never logged or placed in an error detail), one navigation each, block outcome (403, 429 or block marker ends the render with `blocked`, later viewports not attempted); the identity, one-navigation-per-viewport, block-response, block-in-the-second-viewport, fresh-context and mobile-emulation scenarios pass. Applies the sandbox finding of 1.1
- [x] 2.4 Failing tests, then screenshots per viewport with `RENDER_MAX_PAGE_HEIGHT` and `RENDER_MAX_PNG_BYTES`, one failing viewport yielding null with the others kept, `RENDER_TIMEOUT_SECONDS` for the whole render (no browser process outlives a timed-out render) and `RENDER_CONCURRENCY`; the three-screenshots (here two), long-page, one-viewport-fails, timeout and queue scenarios pass (PNG signature checked)
- [x] 2.5 Mutation check; mutations: 45 tried, 45 caught (a first run of 46 left two survivors: the popup test now uses a user gesture, and the import-time pairing loop was a tautology and was replaced by the test-suite check)

## 3. Renderer service and container

- [x] 3.1 Failing tests, then the HTTP service (`POST /render` for one viewport with target, source host, ports, viewport name, that viewport's identity, proxy, deadline; JSON with that viewport's blocks, a base64 PNG and render meta; `GET /health` with the browser version or 503); request validation, size limits, no query or credential in logs; the start-up-check scenario passes
- [x] 3.2 Failing acceptance script first (`scraper/tests/renderer_stack.sh`), then the runtime Dockerfile target `renderer` and `scraper/compose.renderer.yaml`, included by `scraper/compose.yaml` (ADR 0106; no root include line). The worker joins the `render` network and reads `RENDERER_URL` there. Renderer: pinned Playwright and browser, non-root (`iwr`), read-only root filesystem with tmpfs, `no-new-privileges`, `cap_drop`, limits, `shm_size`, networks `egress` and an internal `render`, no host port, an explicit `environment` and no `env_file`, no `DATABASE_URL`, `REDIS_URL` or `MINIO_*`; the not-reachable, no-secrets and start-up-check scenarios pass (`docker compose config`, `docker inspect`, `/health` inside the container)
- [x] 3.3 Mutation check; mutations: 28 tried, 28 caught (18 on the service of 3.1, 10 on the compose file; two of the compose mutants were caught as an invalid config rather than by the intended check)

## 4. Wiring: the run and the ingest (screenshots reach the stack)

- [x] 4.1 Failing tests, then `SCRAPER_RENDER_ENABLED`, `SCRAPER_RENDER_MAX_PER_HOUR` (Redis counter keyed by the UTC hour, shared by workers) and `RENDERER_URL` in the settings (booleans parsed explicitly: `from_env` would read `false` as `True`; startup refusal when `SCRAPER_ATTEMPT_TIMEOUT` is under `RENDER_TIMEOUT_SECONDS` plus 60 s, and `.env.example` sets both), and the render client (one renderer call per viewport in the order desktop, mobile, tablet, each after `limiter.wait_turn` and a `DomainGate` check, a `Retry-After` from a block passed to `defer_for_retry_after`); the firm-own-M2, third-party-M2, firm-own-without-M2, kill-switch, budget-spent, robots-refusal, domain-paused and attempt-timeout scenarios pass over a stub renderer
- [x] 4.2 Failing tests, then the hook in `run_source` (an async callable in `document["render"]`, awaited by ingest after the duplicate check; `render` added to `_PAGE_ONLY_KEYS`; `text`, `content_hash` and `scrape_meta.scraper` unchanged); the text-comes-from-static-parse and unchanged-page-costs-nothing scenarios pass
- [x] 4.3 Failing tests, then ingest of render output: upload PNGs to `shot/{document_id}/{viewport}.png` before the insert, set `screenshots`, `scrape_meta.render` (browser version, `truncated`, `skipped`), schema validation, and removal on duplicate or certainly-uncommitted insert; the duplicate and insert-fails scenarios pass against real PostgreSQL and MinIO
- [x] 4.4 Failing tests, then failure degradation (browser crash, timeout, block, renderer unreachable, upload failure): the document is inserted without `blocks` and `screenshots`, one job error per failed render with `blocked`, `blocked_target`, `storage_error` or `render_failed`, detail free of query, credentials and proxy (through the ingestor's `redact`), and no queue retry or domain cooldown from a render failure; the crash, render-timeout, unreachable and visual-rules-stay-honest scenarios pass
- [x] 4.5 Mutation check; mutations: 39 tried, 39 caught (a sixth survivor was an equivalent mutant: a second `redact` on a detail that `record_error` already redacts, removed from the code)

## 5. Blocks for R4-R8 and R13 (desktop and mobile)

- [x] 5.1 Failing tests on synthetic pages, then the in-page measurement script and its Python wrapper: block selection (nearest block-level element with its own text, no `script`, `style`, `noscript`, `template`), `font_size_px`, `font_weight`, `bbox`, document order, caps (`RENDER_MAX_BLOCKS`, 4000-character text, `truncated`); the small-risk-text, non-text-elements and too-many-blocks scenarios pass
- [x] 5.2 Failing tests, then colour resolution (alpha compositing over the nearest opaque ancestor, `null` for image or gradient backgrounds, `#rrggbb` only); the colour scenarios pass
- [x] 5.3 Failing tests, then `visible`, `in_viewport_on_load`, `requires_interaction` (closed `details`, `aria-controls` with `aria-expanded=false`) and `region` (footer, header, aside, overlay, legal placement-word list with diacritics folded, `main` default, never null); the collapsed-accordion, below-the-fold, footer-legal, cookie-banner, placement-words and region-never-null scenarios pass
- [x] 5.4 Failing tests, then `overflow_clipped` and the same text measured per viewport; the same-text-per-viewport scenario passes and every emitted block validates against the contract's `block` definition (`contracts/validate.py`)
- [x] 5.5 Failing tests, then ingest sets `blocks` on the document and the blocks-reach-analytics scenario passes against real PostgreSQL and MinIO
- [x] 5.6 Mutation check; mutations: 43 tried, 41 caught (two equivalent: `visible` already false for a closed `details` through `checkVisibility`, and the in-page cap `>=` against `>` gives the same output once Python slices and flags the surplus)

## 6. Tablet viewport (first to drop if time is short)

- [x] 6.1 Failing tests, then the `tablet` context (820x1180, `has_touch`, the run's identity), its screenshot at `shot/{document_id}/tablet.png` and its blocks; the three-screenshots scenario passes with all three keys set
- [x] 6.2 Mutation check; mutations: n/a, the tablet viewport is a table entry and the call order a tuple, both pinned by the group 3 and 4 mutants (viewport width, order, per-viewport blocks)

## 7. End to end and closing

- [x] 7.1 End-to-end check on docker compose: `scraper/tests/test_e2e_render.py` with the real renderer container (`renderer-e2e`, `--profile e2e`), two synthetic demo pages (`tests/fixtures/demo`; the saved XTB and mBank pages are not in the repository), Collector, Ingestor, Redis, PostgreSQL and MinIO as in `app.py`: each seeded `firm_own` + `M2` source yields 24 schema-valid blocks over desktop, mobile and tablet and three PNGs in `iw-raw`, and a rerun adds no row and no object (2 passed). The `api` screenshot route is not in this stack and was not exercised
- [x] 7.2 Payload measured on the demo pages: `documents.payload` is 9.2 KB (xtb) and 9.0 KB (mbank) with 24 blocks; a real broker page will have more (cap 600 blocks per viewport, 4000 characters each); `GET /api/findings/{id}` was not measured because `api` is not in this stack
- [x] 7.3 Docs updated (`scraper/CLAUDE.md`, `scraper/README.md`, `scraper/.env.example`, the conventions skill, `.docs/analytics-plan.md` §5, `.docs/status/scraper.md`, ADR 0107 listed), `docs-check` ok, `pip-audit` on the four requirements files clean and recorded in `.docs/security-audit.md`, `iw-ai-log` row added
- [x] 7.4 Run the `iw-pr-review` skill and fix real findings; `iw-reviewer` reports no open blocking findings

## 8. Review fixes on PR #67

- [x] 8.1 Failing tests, then the fix: a redirect hop of any request (image, stylesheet, fetch, iframe, a later hop of a longer chain, a closed port) fails the render after the screenshot; `SharedWorker` removed in every frame
- [x] 8.2 Mutation check; mutations: 3 tried, 3 caught (sweep disabled, `SharedWorker` left in place, only the first hop judged)

## Deferred follow-up (not part of this change's done criteria)

- `occluded` on `block` (design open question 1; Damian suggests `boolean | null`, null = not measured): only if the whole team accepts the contract change after Integration #1 (`IW_CONTRACT_CHANGE=1`); then a failing test with a sticky bar over a risk text and a `document.elementFromPoint` measurement, as its own small change. Nothing in groups 1-7 depends on it.
- `sources.config` column for per-source render and parser options: a proposal for Damian after the hackathon.

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
