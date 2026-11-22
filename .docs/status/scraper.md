# Status: scraper

Covers `scraper/`; whoever changes it updates this file (owners: [`.github/CODEOWNERS`](../../.github/CODEOWNERS)). Last updated: 2026-11-22 (Sun).

## State

- SDLC merged.
- `scraper-v1` (fetch, parse, politeness, guards) is merged (PR #19).
- `scraper-ingest` (database sink, `documents`, `iw:documents`, republish sweep) is implemented against Damian's `0001_initial`, in review (PR #22) and archived in that PR.
- `scraper-orchestration` (queue, run lock, concurrency cap, events, scan requests, scheduler, health, `run_source`, the `worker` and `scheduler` commands) is implemented and tested end to end on real Redis, PostgreSQL and MinIO; the opt-in live KNF smoke run passed once (2026-11-21). The PR is next.
- `scraper-stack` deploys the scraper in the one-command stack (`scraper/compose.yaml`: `worker`, `scheduler`, `seed`; `scraper/tests/stack.sh`; ADR 0106; `seed` rejects an invalid cron). Implemented and checked locally (12 config + 10 run scenarios, 13 mutations caught); PR next.
- `content-hash-definition` (issue #31): the `content_hash` definition (NFC) is written into integration-plan §3 and ADR 0105, pinned by scraper tests; no scraper code changed. Analytics (Damian) still has to read the stored hash instead of recomputing it with NFKC (proposal in the issue).
- `scraper-v2-social` (Telegram public channels, ADR 0103) is implemented on top of `scraper-orchestration`: parser, collector registry, bounded paging in `run_source`, seeds loaded by the `scraper-v2-sources` directory loader; the store lists `Source.collectable` rows, not only `web`. PR #61.
- `scraper-effectiveness-report` is implemented and reviewed (`python -m iw_scraper.report`, a read-only summary of collected documents and job errors from the shared tables; no success rate, because only the last run per source is stored). The PR is next; a REST route or dashboard widget for it is a follow-up for Damian and Kacper.
- `scraper-sample-import` (`python -m iw_scraper.sample_import`: saved HTML or text, for the samples handed out at the stand and offline demo replay, through the same `Ingestor`) is implemented and tested; rehearsed in the image on two saved pages, not through the full stack (analytics findings and the dashboard alert not exercised). PR #56.
- `scraper-rescan-tracking` (issue 71, scraper half) is implemented, reviewed per group and archived in its PR: an edited web page reports `previous_document_id` and a `rescan_outcome` log line, a removed one (404/410 confirmed once) is an `http_error` `HTTP 404`/`HTTP 410` job error with the source URL (what the api reads; a redirecting source needs the api to match by `source_id`) and ends the run `ok`; ADR 0110. The api and dashboard derive the labels (queries on issue 71); revert and reappear are known limits until Damian decides on a `last_seen_at` column. Merge order: `scraper-social-x-youtube` restructures the web flow in `collect.py` and merges first; this branch then rebases.
- ADRs 0101 and 0102 are accepted (PR #19); ADR 0104 (ingest order, republish sweep) takes effect when PR #22 merges; ADR 0103 (Telegram first) takes effect when the `scraper-v2-social` PR (#61) merges.

- `scraper-v2-sources` (12 vetted M1/M2/M3 web sources in `scraper/seeds/sources.toml`, validated and idempotent seed loader, host-guard test, opt-in live check) is implemented and tested, stacked on `scraper-orchestration` (PR #38). The opt-in live check passed for all 12 pages on 2026-11-21 (HTTP 200, no redirect, robots allowed, text present). M3 positives come from `scraper-v2-social` (Telegram channels) and the icobench list page; naming a business from the KNF warnings list is an optional, human-only follow-up.

- Social R&D (ADR 0109, docs-only PR): X tweets are collectable with a dedicated account's cookies (Playwright reading the page's GraphQL); YouTube metadata works anonymously through our fetch layer; YouTube transcripts work through audio plus local Whisper (residential proxy, Node 22, PO token server), not through the caption URL (429 from the home IP). Specs `scraper-social-youtube` (metadata only) and `scraper-social-x` follow.

- Hand-in (issues #77 and #74, scraper part): `.docs/presentation-scraper.md` has five slides with speaker notes (architecture, safety, coverage on the 223 documents of #78, add-a-source example, AI-assisted process), every number sourced from `origin/main`; X and YouTube collectors and re-scan tracking are labelled "in progress, not merged". Docs-only, no OpenSpec change.

## Demo rehearsal (issue #78)

Source: Damian's recorded run in the issue (clean `docker compose up` from `main` c810a14, one `POST /api/scans` per seeded source, all 202), read against the code; I did not rerun the stack. Since c810a14 scraper code changed on `main` only for the renderer (PR #67, merged 00:24Z, after the run, off by default) and refactors made for it (`blocking.py`, `addresses.py`; not checked as behaviour-neutral), so the run's scraper is the current one without rendering, as far as that check goes.

What the scraper did:

- Sources: 17 seeded = 13 web (12 in `seeds/sources.toml` plus the KNF row `seed.py` inserts) and 4 Telegram channels (`seeds/telegram.toml`). The `seed` one-shot gates `worker` and `scheduler` in `scraper/compose.yaml`, so the rows existed before the scans.
- Jobs: 17 scan requests became 17 manual jobs (`scan_requests.py` enqueues `execute_job` with id `scan-<message id>`): 13 web, 4 Telegram. A Telegram job pages the channel until `SOCIAL_MAX_POSTS` (default 40) posts were seen. The run stored 50-55 per channel, more than 40, so a third page was read; the live page size is not recorded.
- Documents: 223 on `iw:documents`, from all 17 sources (Damian). Web pages gave 1 each (13), so the 4 channels gave 210 by difference (50-55 each, Damian). The per-source split is not in the issue.
- Errors and retries: 0 `job_errors` (Damian). A transient failure records a job error on every attempt (`jobs.py`), so none means no failed attempt and no retry, apart from a requeue after a lost Redis or database connection (`jobs.py`), which records none. Deferrals (a `Retry-After` or failure pause) leave no job error and were not checked.
- Not checked: scraper logs and `scan.*` events (not quoted in the issue), timings, and `python -m iw_scraper.report` output.

Scheduler and cron: not checked. The run used manual scan requests only. The `scheduler` enqueues a source only when its cron matches one of the last five minutes (`scheduler.py`), crons are UTC (KNF `0 */6 * * *` by default, `SCRAPER_SEED_CRON`; web daily or weekly from 06:00; Telegram `15`, `25`, `35`, `45` past every sixth hour), so whether a slot fell inside the run is unknown. `tests/stack.sh` asserts the scheduler stays up, not that a scheduled scan lands documents. A scheduled-scan check needs a run where a source's cron falls due while the scheduler is up (for example `SCRAPER_SEED_CRON="*/5 * * * *"` for the KNF row), with the resulting documents or `scan.*` events recorded.

Gaps that matter for the demo:

- No `blocks` or `screenshots` on any document: the run had no renderer. With `SCRAPER_RENDER_ENABLED=true` the five `firm_own` M2 pages (3 XTB, 2 mBank) are rendered; that path is tested on demo pages, not on the live stack, and not through analytics. Damian's table lists M2 rules R2, R3, R14 and R18 (uncertain) only; no visual R4-R8 or R13 appears there (my reading of the table).
- Telegram volume: 210 of 223 documents are channel posts, and they drive the low M1 noise on the controls (Rare Crypto Signals 26, KDP 17; Damian). Rule matching is analytics; the scraper stores every post with text.
- The M3 false positive (Grant Thornton control) and the hosted-LLM outage are analytics findings, not scraper ones.
- Re-running the same sources creates no new documents (dedup by `content_hash`), so a second rehearsal shows the scan events but no new findings; use a fresh database or a changed page for a live demo of a scan.

- `scraper-social-x-youtube` (X over Scweet from the home IP with a dedicated account's cookies; YouTube through our fetch layer with transcripts through a residential proxy, no Whisper; ADR 0109; seed rows in `scraper/seeds/x-youtube.toml`, no schedule so a scan request is the only trigger) is implemented and tested end to end on the test stack with saved real answers. First live run (2026-11-22, the production wiring on the test services, real network, the dedicated cookies and a residential proxy): X `@uknf` stored 24 posts from one Scweet call (cap 40) with the author's follower count, no job error; YouTube `@UKNFpolska` with `YOUTUBE_MAX_VIDEOS=3` stored 3 videos, each with its caption transcript (one transcript is about 80,000 characters, a long webinar), no job error. One run per platform: the restriction and block paths are tested against injected errors only. The PR is next.

## First-run rehearsal (`first-run-bootstrap`)

Clean project from this branch (2026-11-22, one `docker compose up -d --build --wait` on empty volumes, rules-only analytics because no LLM key was set, renderer off, real network): `up --wait` returned after 37 s with images already built (a cold image build was not timed); `bootstrap` exited 0; about three minutes later `status` reported 17 of 17 scheduled sources `scanned`, the 2 X and YouTube rows `manual`, 223 documents, findings M1 53, M2 5, M3 12 and 19 calibration points per module, and exited 0 (ready). A first read, about one minute after `up`, showed 15 scanned, 2 pending, 153 documents. Not checked: a cold build time, a run with the LLM on, a scheduled scan landing by cron, a rerun on the same volumes beyond the `stack.sh` check (no new requests).

## Rehearsal on `main` 313c625b (2026-11-22, own project name, own volumes)

- Cron: the KNF row's `schedule_cron` set to `*/5 * * * *` through `PATCH /api/sources/{id}` (the seed one-shot does not change an existing row). The scheduler enqueued `sched-<source>-20261122T0510Z`, the worker ran it and `iw:events` carried `scan.started` 05:12:34Z and `scan.finished` 05:12:43Z (`documents` 0, `status` ok: the page was unchanged). The job ran two minutes after its slot because the worker was busy with renders; the scheduler's five-minute look-back still caught it.
- Render: with `SCRAPER_RENDER_ENABLED=true`, R4 and R6 returned `pass` on rendered XTB and mBank findings (`GET /api/findings?module=M2`, `rules[].result`), and `not_applicable` on a document stored after a failed render. Five simultaneous scans overloaded the one-at-a-time renderer: renders of 8-85 s, `render_failed` job errors ("renderer did not answer", "render exceeded"), repeated arq retries with `run lock lost` warnings, and no document stored for minutes. Default stays off; the `.env` line is `SCRAPER_RENDER_ENABLED=true` (in `.env.example`, commented in `scraper/README.md`).
- Not checked: a solo render timing on an idle renderer, rendering in the first-run bootstrap with the flag on from the start.

## Active OpenSpec changes

- `scraper-rescan-tracking` (issue 71: edited and removed web pages)
- `first-run-bootstrap` (this PR): a one-shot `bootstrap` queues one scan per active source with a cron that never ran, `python -m iw_scraper.bootstrap status` reports readiness, `.docs/brief-compliance.md` maps the brief to evidence; see "First-run rehearsal" below.
- `scraper-v3-render` (merged, PR #67, 2026-11-22 00:24Z): isolated Playwright renderer service, per-viewport screenshots and `blocks` for `firm_own` + `M2` sources, off by default (`SCRAPER_RENDER_ENABLED`);
- `scraper-source-discovery` (`python -m iw_scraper.discover`: inactive candidate sources from stored links, ADR 0108; implemented, in review);
- `scraper-stack` (PR #52); `scraper-orchestration`, `scraper-author-provenance`, `scraper-v2-sources` and `content-hash-definition` are merged (PRs #38, #49, #41, #43, #44)
- `scraper-effectiveness-report` (PR #57)
- `scraper-sample-import` (PR #56)
- `scraper-audit-in-pr-body` (issue #66): spec-only delta so `scraper-deployment` says the `pip-audit` result goes in the PR body (ADR 0209); no code or doc edit.
- `compose-include-chain` (issue #97): `scraper/compose.yaml` includes `../scraper/compose.renderer.yaml`, so the documented `-f infra -f api -f scraper` chain resolves; `stack.sh` root group checks it.

## Blockers and open decisions

- `scraper-v3-render` adds to `scraper/compose.yaml` only the `include` of `compose.renderer.yaml`, the `render` network and the worker's renderer settings, keeping `stop_grace_period` 60 s (ADR 0106); the root `compose.yaml` needs no new line.
- Wiring (`Ingestor`, `sweep`, `Storage.check_bucket`, the job-error sink) is done in `scraper-orchestration` (`app.py`).
- Three redactors exist: `reporting.redact` (userinfo only, used by `fetch.py` and `reporting.py`), `logs.redact` (URL and DSN secrets, used by the JSON log formatter) and `ingest.errors.redact` (full). Keep the full one and drop the others when `scraper-orchestration` wires the pieces (follow-up 3 of `scraper-ingest`).
- Issue 36 (author provenance): no collector on `main` sets `author`; the ingest drops it from a page. A `scrape_meta` "author verified" flag would need a contract change and is only proposed (`scrape_meta.author_source`, in the issue 36 reply), not in the contract; its PR must keep the flag off a page-supplied `scrape_meta`.
- `scrape_meta.scraper` is settled without a contract change: `httpx` plus `scrape_meta.client` (ADR 0101).
- The real UKNF sample format is unknown until the stand: `sample_import` reads HTML, `.txt` and `.md`; a PDF or DOCX reader is one function in `READERS`, added on the day.
- `blocks`/`screenshots` (rules R4-R8, R13) come from the `renderer` service (ADR 0107) once `scraper-v3-render` merges; the worker joins the `render` network through `scraper/compose.yaml`, and render stays off until `SCRAPER_RENDER_ENABLED=true`.
- Social media: Telegram first (ADR 0103). The brief's Facebook, Instagram and TikTok are not covered (login walls, a JavaScript shell); a `telegram` platform value waits for contract v2 (issue 34).
