# Tasks

## 1. ADR drafts and agreements (human decides)

- [x] 1.1 Read the installed noble-tls, curl_cffi and httpx APIs and draft options in `.docs/decisions/` for the fetch client; verify with `node .claude/skills/iw-docs-update/scripts/docs-check.mjs`
- [x] 1.2 Draft options for the job queue/scheduler and for the first social platform note; same docs-check passes. Group 6 waits for the queue ADR to be decided by a human.
- [ ] 1.3 Agree with C on the `scrape_meta.scraper` value for a TLS-impersonating client (the v1 enum is `playwright|httpx|api|manual`, so a TLS client fits none honestly: use an existing value or request a v1 enum addition before the freeze); recorded in ADR 0101 and `contracts/`. Group 3 waits for this.
- [ ] 1.4 Agree with C who creates the Alembic migration for the `documents` unique index `(source_id, content_hash)`, the `job_errors` table and the published marker (`.docs/integration-plan.md` §7: migrations live in `api`, A never creates tables by hand; `api/` does not exist yet); recorded as an open item in `.docs/STATUS.md`. Group 5 waits for this.

## 2. Scraper skeleton and parser

- [ ] 2.1 Failing test, then `scraper/` package with pinned deps and a pytest setup; `pytest scraper` runs green on an empty parse
- [ ] 2.2 Failing tests, then HTML-to-fields parser for `title`, `text`, `canonical_url`, `links` against saved fixtures in `scraper/tests/fixtures/` (article page, empty page, malformed page); the article, `empty_text` and `parse_error` scenarios pass

## 3. Fetch layer and failure detection

- [ ] 3.1 Failing tests, then `fetch(url, identity)` over the ADR-chosen client with timeout and retry cap; the timeout and `http_error` scenarios pass against a local stub server, no live network
- [ ] 3.2 Failing tests, then block detection (403, 429, captcha marker, empty body) and `Retry-After` handling; the blocked and Retry-After scenarios pass
- [ ] 3.3 Failing tests, then `robots.txt` check and per-domain rate limit; the robots scenario passes
- [ ] 3.4 Failing tests, then one identity (proxy, user agent, headers, TLS profile) fixed per session and rotated whole on a block signal; the identity scenarios pass

## 4. Source selection and untrusted-content rules

- [ ] 4.1 Failing tests, then selection of active `web` sources with `source_kind` copied from the row; the three source-selection and source-kind scenarios pass
- [ ] 4.2 Failing tests, then the host allow-list (hosts of active `sources` rows plus configured extras) applied to the source URL, every redirect hop and every URL taken from scraped content, plus refusal of private, loopback, link-local and compose-internal addresses after DNS resolution; the allow-list, redirect and private-address scenarios pass

## 5. Ingest (after 1.4)

- [ ] 5.1 Failing tests, then schema validation against `contracts/` before insert; valid and `schema_invalid` scenarios pass (needs `pip install -r contracts/requirements.txt`)
- [ ] 5.2 Failing tests, then `content_hash`, a dedup check before any upload, and insert with `ON CONFLICT DO NOTHING` on the unique `(source_id, content_hash)`; rerun, changed-page and no-stray-object scenarios pass against a real PostgreSQL and MinIO from docker compose
- [ ] 5.3 Failing tests, then HTML upload to `iw-raw` and `html_object_key`, with the object removed when the insert yields no row; stored, `storage_error` and no-stray-object scenarios pass
- [ ] 5.4 Failing tests, then `XADD iw:documents` after commit with `publish_failed` recording and a republish sweep over unpublished rows; event-after-commit, insert-fails, Redis-down and sweep scenarios pass
- [ ] 5.5 Failing test, then `job_errors` rows and a JSON log line for every reason code, with credentials never recorded; each reason from the specs and the no-credentials scenario are asserted

## 6. Scheduling and end to end

- [ ] 6.1 Failing test, then wire the ADR-chosen queue/scheduler to run collection from `schedule_cron`; one scheduled run over a fixture source ends with one document and one stream entry
- [ ] 6.2 Failing end-to-end test on docker compose, then fix what it shows: a fixture source yields a schema-valid `documents` row, a MinIO object and an `iw:documents` entry, and a rerun adds nothing

## 7. Closing

- [ ] 7.1 Apply the `iw-docs-update` skill (`scraper/CLAUDE.md`, your row in `.docs/STATUS.md`, ADR drafts), run docs-check, and add the `iw-ai-log` row
- [ ] 7.2 Run the `iw-pr-review` skill and fix real findings; `iw-reviewer` reports no open blocking findings

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
