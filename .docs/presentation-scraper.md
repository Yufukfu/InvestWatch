# Presentation: scraper section (architecture, safety, coverage, extensibility, AI process)

Slide content for the hand-in PDF (issues #77 and #74). Kacper pastes it into the deck; each `##` below is one slide, with speaker notes under **Notes**. Owners: see [`.github/CODEOWNERS`](../.github/CODEOWNERS).

Every number was checked on `origin/main` at `a706474` (2026-11-22), against the code, the ADRs, `git` or `gh`; the source of each is named on its slide. Coverage numbers (slide 3) are Damian's recorded run in issue #78 (clean `docker compose up` from `main`, 17 seeded sources, one `POST /api/scans` each); they are not recomputed here. Counts that move (PRs, log rows) were taken at the commit above: refresh them with the commands under slide 5.

**Not on `main` at the time of writing** and therefore not claimed as capabilities: X and YouTube collectors (branch `scraper/scraper-social-x-youtube`, local, not pushed) and re-scan tracking of removed or changed pages (branch `scraper/scraper-rescan-tracking`, local, not pushed). They appear only on slide 3, labelled "in progress, not merged".

---

## 1. Scraper: queue, fetch ladder, one writer

Scheduler or dashboard scan request → Redis queue → worker → one `ScrapedDocument` row plus raw HTML → event for analytics. The scraper knows nothing about analytics.

```
scheduler / POST /api/scans ─▶ arq queue (Redis) ─▶ worker: run_source
   robots → fetch (TLS client) → parse → Ingestor
      ├─ validate against contract v1, dedup by content_hash
      ├─ raw HTML ─▶ MinIO bucket iw-raw
      ├─ INSERT documents (PostgreSQL)
      └─ XADD iw:documents {document_id, schema v1}  ─▶ analytics
```

- **Fetch ladder, cheapest first:** the rule is the site's own JSON endpoint, then a TLS-impersonating client, then Playwright last. Today two rungs are implemented: the TLS client (`noble-tls`, profile `CHROME_146_PSK`; ADR 0101) and the optional renderer. Playwright runs only in a separate `renderer` service, only for `firm_own` sources that target M2 (screenshots and layout blocks for the visual rules), and is **off by default** (`SCRAPER_RENDER_ENABLED=false`; ADR 0107, merged in PR #67).
- **Queue and schedule:** `arq` on the Redis we already run (ADR 0102); one job per active source and cron slot, with a unique job id per slot so a second scheduler cannot double-enqueue. Retries and backoff live only in the queue.
- **One writer:** `Ingestor` is the only path to `documents`: upload HTML, insert with a named `ON CONFLICT (source_id, content_hash)`, then `XADD`. Delivery is at-least-once; a sweep republishes rows whose announcement was lost (60 s grace); the stream is capped with `MAXLEN ~ 10000` (ADR 0104).
- **Deploy:** one image, three services: `worker` (scale with `docker compose up --scale worker=3`), exactly one `scheduler`, a one-shot `seed` (ADR 0106). No scraper container publishes a host port.

**Notes:** The ladder is a rule, not a hope: anything that fetches goes through the same guards, limiter and identity, including the renderer, so a heavier rung never bypasses politeness. Limits (`worker` 1 CPU / 768 MB, `scheduler` 0.5 CPU / 256 MB, `seed` 0.5 CPU / 128 MB) are first estimates, not measured on the demo machine; the renderer is another container (about 360 MB image, 1.5 CPU / 1 GB at most) and it did not run in #78. Scaling is safe for `worker` (queue, per-domain limits and the run lock are in Redis); `scheduler` stays at one. Scan events (`scan.started`, `scan.finished`) go to `iw:events` for the dashboard. Sources: `scraper/README.md`, `scraper/CLAUDE.md`, ADRs 0101, 0102, 0104, 0106, 0107, `.docs/integration-plan.md` §2, §3.

---

## 2. Polite, hard to abuse, honest about provenance

The scraper fetches addresses that people and seeds hand it, so every request is checked before it is made, and nothing a page says about itself is trusted.

- **Politeness:** `robots.txt` read with `protego` under the product token `InvestWatch`; an unreadable file (429, 5xx, timeout) disallows the run, a 4xx means no restrictions (RFC 9309). At least 5 s between request starts per domain across all workers, 2 jobs at once per domain, `Retry-After` honoured, a domain paused after 5 consecutive failed jobs (defaults in `.env.example`).
- **Anti-block:** a session is one attempt (fresh cookies). One identity per run, drawn from a table of three desktop Chrome identities where user agent, client hints and TLS profile always travel together. A proxy is picked per request from `PROXY_LIST` (a 407 puts it on a 90 s cooldown). A block (403, 429, captcha marker, empty body) ends the run and is never retried; a `robots.txt` refusal is not a block.
- **Address guards (SSRF):** every URL (source, each of up to 5 redirect hops, each link) must be http(s), on an allow-listed host, port 80 or 443, resolve through our own DNS to a public address only, and the connection goes to the address that was checked. Links found on pages are stored, never fetched. The renderer holds no secret and sits on no data network.
- **Credentials never leave:** proxy URLs are never logged (an identifier `proxy-xxxxxxxx` is); URL and DSN secrets are redacted in log lines and in `job_errors.detail`; failures use a closed set of reasons.
- **Provenance and identity of content:** `author` is set only by a platform collector from the platform's own account fields (Telegram: the handle from the source URL), never from `<meta>`, `rel=author` or embedded JSON that the post's writer controls (PR #41, issue 36). `content_hash` is sha256 of the text after Unicode NFC and whitespace collapse, case kept, pinned by tests with literal hashes (ADR 0105).

**Notes:** Why author provenance matters: analytics routes a post to M2 ("the firm's own marketing") from `author.handle`, `author.profile_url` and the host of `url`, so a scammer who writes `<meta name="author" content="XTB">` must not become the firm. Before PR #41 the ingest copied `author` from any parsed page; it now drops it. Honest residuals, all recorded in the ADRs: with a proxy, the proxy resolves the name itself, so the address check is advisory there; the renderer's Chromium cannot pin the checked address (DNS rebinding) and may request a redirect hop before the render is rejected (ADR 0107); redaction exists as three small functions (`logs.py`, `reporting.py`, `ingest/errors.py`), a known duplicate to merge. Telegram's terms for collecting public previews were not researched (ADR 0103). Sources: `scraper/src/iw_scraper/{robots,ratelimit,domaingate,proxy,identities,targets,addresses,blocking,fetch}.py`, `scraper/README.md` "Author provenance", ADRs 0101, 0103, 0105, 0107.

---

## 3. Coverage on real data: 17 sources, 223 documents

One clean `docker compose up` from `main`, one scan request per seeded source (all accepted with 202), recorded by Damian in issue #78.

| Source kind | Sources | Documents |
|---|---|---|
| Web pages (KNF warnings list plus 12 vetted pages: 5 firm sites for M2, 4 third-party for M1, 2 negative controls for M3 and 1 list page for M1 and M3) | 13 | 1 each (13) |
| Telegram public channels (`t.me/s/<handle>`) | 4 | 50-55 posts each (the rest of the 223) |

- **What came out of it:** all 223 documents were consumed by analytics with 0 errors and 0 poison messages; 72 findings (M1 54, M2 5, M3 13) and 10 `finding.high_risk` events (analytics' own result, #78).
- **Social on `main`:** Telegram public channels only, one document per text post, with its permalink and the channel as author (ADR 0103, PR #61). Facebook, Instagram and TikTok (named in the brief) are **not** covered: login walls or a JavaScript shell (evidence in ADR 0103).
- **In progress, not part of this submission:** X and YouTube collectors, and re-scan tracking (a removed or changed page). X needs a dedicated account's cookies and its `robots.txt` disallows everything, so ADR 0109 (merged) records it as a documented, owner-approved exception to our robots rule; none of it is implemented on `main`. Neither runs in the product today.
- **Gaps we know:** the renderer (screenshots, layout blocks) is merged and off by default and the #78 run had no renderer, so no document has blocks or screenshots; the visual M2 rules need its layout blocks; no real UKNF samples yet (`sample_import` is ready for them, #73).

**Notes:** The 13 web pages and 4 channels are 17 rows in `sources`, which is what `seed` loads (`scraper/seeds/sources.toml` has 12 tables, `telegram.toml` 4, plus the KNF row from the loader). 223 minus the 13 web pages gives the 210 Telegram posts; Damian reported the per-channel range, not the sum. `SOCIAL_MAX_POSTS` defaults to 40 posts seen (`collect.py`, documented as two pages of twenty), yet #78 recorded 50-55 per channel; the reason is not checked, so do not present 40 as the observed size. No source row says that a named business breaks a rule: each is a page that matches a signal, a negative control, or a list page. The Grant Thornton negative control produced a high-risk finding because the hosted LLM was down (#78, gap 2): that is an analytics-side result (#78). Sources: issue #78 comment, `scraper/seeds/*.toml`, `scraper/README.md`, ADRs 0103 and 0109, `git ls-tree origin/main`, `gh pr list`.

---

## 4. Open for extension: a source in one table, a platform in one module

Two different extensions, with real sizes. No change to the queue, `run_source`, ingest or the contract in either.

**A new source: seed rows only, no Python.** Real commit `b3b37bd` (the four Telegram channels): `scraper/seeds/telegram.toml` +38 lines for four sources (7 lines each), plus a 60-line test. Shape of one row:

```toml
[[source]]
name = "Rare Crypto Signals (Telegram)"
platform = "other"
url = "https://t.me/s/rarecryptosignals"
source_kind = "third_party"
target_modules = ["M1"]
schedule_cron = "15 */6 * * *"
```

Then `python -m iw_scraper.seed` (runs on every `docker compose up`): all seed files are validated first, then rows whose URL is new are inserted; a source edited in the dashboard is never overwritten. The 12 web sources are the same shape (`8e2d46d`).

**A new platform: one parser module and one registration line.** The registry maps a host to a collector (`scraper/src/iw_scraper/social/registry.py`):

```python
registry.register("t.me", telegram.parse, valid_url=telegram.valid_url)
```

`parse(body, final_url) -> Channel` is the whole contract of a collector. Fetching, robots, limits, guards, identity, proxy, ingest and the `author` handling are shared.

**What it really took (Telegram, `49ca3e6`):** +247 lines of source (`telegram.py` +192, `registry.py` +28, `ingest/document.py` +17, `types.py` +9, a one-line `__init__.py`) and +464 lines of tests and saved fixtures. That commit also created the registry and the post identity hash, so it is larger than a second platform should be; no second platform is merged to prove it (X and YouTube are in progress, slide 3).

**Notes:** Be honest on stage: "add a collector in N lines" is true for a source (7 lines of TOML) and for the registration (1 line); the parser itself is a module of about 150 lines today (`telegram.py`) plus tests. A new `platform` value is a contract change, so Telegram documents carry `platform = "other"` and `scrape_meta.network = "telegram"` until contract v2 (issue 34). The platform-neutral `Channel` model was split out after the first commit (`c091c98`). Checklist for the next platform is in `scraper/CLAUDE.md`, "Adding a social platform": check it is robots-allowed and anonymous (or write an ADR exception, as 0109 does for X), saved real pages as fixtures, an opt-in live smoke test, a seed row. Analytics' counterpart, a new rule in two files, is slide 6 of the analytics section. Sources: `git show --numstat 49ca3e6 b3b37bd`, `scraper/src/iw_scraper/social/`, `scraper/seeds/`, `scraper/README.md` "Run".

---

## 5. AI-assisted process: spec, test, review, record

Every change goes spec first, test first, reviewed by a second agent, and recorded; guards that matter are code, not prompts.

- **Spec-driven:** OpenSpec proposal, a human approves, `/openspec-apply-change` per task group, archive as the last commit. At `a706474`: 56 archived changes (12 of them the scraper's), 31 specs, 33 ADRs (9 of them the scraper's, 0101-0109).
- **Per task group:** a failing test first, a hand-written mutation check on every guard, then the read-only `iw-reviewer` agent on that group's own pinned `BASE..HEAD`. Every finding is verified against the code before it is fixed or rejected. Skills: `iw-implement`, `iw-commit-cycle`, `iw-pr-review`, `iw-docs-update`, `iw-ai-log`, `iw-scraper-conventions`, `iw-watch`.
- **Deterministic guards:** a tested git hook denies force push, any push to `main`, amending a pushed commit, a staged `.env`, `console.log` in JS/TS, service code with no active OpenSpec change, and (since Sat 14:30) contract edits.
- **Evidence trail:** 77 rows in the AI log (`.docs/ai-workflow.md`, 15 of them Adam's); 15 merged PRs from `scraper/*` branches, each merged by the human.
- **A rule that misled us:** the agent assumed the shape of Damian's `documents` table (a `committed_at` column, a bucket-creating startup). Damian's real migration differed, so `scraper-ingest` was rebuilt against it. Now: read the peer's branch early, never a guessed schema, and `scraper/CLAUDE.md` says the schema is Damian's (Alembic in `api/`, never create or alter a table in the scraper).

**Notes:** What review caught that green tests had not (log rows, `scraper-v1` and `scraper-ingest`): the standard-library `robotparser` ignores `*` and `$` rules; NAT64, IPv4-compatible and site-local IPv6 addresses passed the SSRF guard; a proxy password could reach an error text; redaction missed 9 of 10 credential forms; blank text was stored as a junk row. Mutation runs also showed four of our own tests could not fail. A second honest limit: the stale local checkout of `main` misled the author-provenance answer on issue 36 until the agent read `origin/main`; the draft was also wrong about the unmerged Telegram branch until the security review checked the code. The human decides every push and merge (hard rule in `CLAUDE.md`); the hook catches mistakes, not a determined agent, and review is a practice, not a hook. Refresh the counts: `ls openspec/changes/archive | wc -l`, `ls .docs/decisions | grep -c '^0[1-3]'`, rows of the Log table in `.docs/ai-workflow.md`, `gh pr list --state merged --json headRefName`. Sources: `.docs/ai-workflow.md`, `.claude/SDLC.md`, `.claude/agents/iw-reviewer.md`, `.claude/hooks/git-guard.js`, `scraper/CLAUDE.md`.
