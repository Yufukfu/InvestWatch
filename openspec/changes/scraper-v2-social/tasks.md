# Tasks

Each group from 1 on is one commit. Its first task is the failing test and its last is the mutation check (`iw-commit-cycle` step 3), completed as `mutations: N tried, N caught` (or `mutations: n/a, <reason>`). Starts after `scraper-orchestration` is merged: rebase on `origin/main` first. The real channel pages used as fixtures are copied from the research samples in the session scratchpad (`.../scratchpad/social/out/`, among them `rarecryptosignals`, `crypto_sygnaly`, `subetradingpl`, `kdpwiadomosci` and the `?before=2000` page; the draft parser is `tgparse.py` there); check that they are still public before saving, and keep the saved files free of anything but public channel markup.

## 1. Parser and registry

- [ ] 1.1 Copy the real channel pages into `scraper/tests/fixtures/` (plus a header-only page, an image-only page and a no-preview redirect body). Failing tests for "Text post", "Post with a line break", "Image-only post", "Page of image-only posts", "Subscribers with a suffix", "Small plain count", "No counter", "Short channel" (no older link) and "Page that is not a channel", then the Telegram parser: header, posts (id, text, time, permalink, views, links, per-post HTML) and the older-posts link
- [ ] 1.2 Failing tests, then the collector registry keyed by host ("Host with a collector", "Duplicate registration") and the widened selection ("Social source with a collector is selected", "Non-web source is skipped" (now: with no collector for its host), plus the unchanged web scenarios)
- [ ] 1.3 Failing tests, then `build` of the contract fields per post (`platform` and `source_kind` from the row, `published_at` UTC, `author`, `links`, `scrape_meta` with `message_id` and `views`), validated against `scraped-document.schema.json` in the test; the "Text post" and "Post markup is the stored HTML" scenarios pass
- [ ] 1.4 Mutation check; line reads `mutations: N tried, N caught`

## 2. Run and paging

- [ ] 2.1 Failing tests over stubbed stages, then the social branch of `run_source`: URL form check (`invalid_request`), robots, one fetch per page through the limiter and guards, paging by the `before` link up to `SOCIAL_MAX_POSTS`, early stop when a whole page is `duplicate`, "no public preview" as `parse_error`, a later-page failure keeping earlier documents; the "Accept only a public channel URL", "Paging is bounded and stateless", "Channel without a public preview" and "Failures never produce a document" scenarios pass
- [ ] 2.2 Failing tests, then the links rule: `x.com`, YouTube and `t.me` links kept in `links` and never requested (a stub server records requests); the "Links are pointers, never fetched" scenarios pass
- [ ] 2.3 Mutation check; line reads `mutations: N tried, N caught`

## 3. End to end

- [ ] 3.1 Failing end-to-end test on docker compose: a seeded `platform = other` source on a local stub that serves a saved channel page (two pages) yields schema-valid `documents` rows with per-post MinIO objects, `iw:documents` entries and `scan.finished`; a rerun adds nothing and requests only one page. `SOCIAL_MAX_POSTS` is in `.env.example`
- [ ] 3.2 Opt-in live smoke test (marker `scraper_live`, deselected by default and outside CI) that collects one public channel once through the full stack; its handle comes from an environment variable
- [ ] 3.3 Mutation check; line reads `mutations: n/a, end-to-end and smoke tests only` unless code changed

## 4. Closing

- [ ] 4.1 Apply the `iw-docs-update` skill: write ADR 0103 as accepted (decision Telegram, human decision of 2026-11-21, the options and evidence listed in `design.md`) and update its row in `.docs/decisions/README.md` (it says "proposed"); update `scraper/CLAUDE.md`, `iw-scraper-conventions` (social collectors by host, per-post HTML, links as pointers, X and YouTube not collected), `scraper/README.md` (`SOCIAL_MAX_POSTS`, the Telegram source URL form), `.docs/integration-plan.md` §3 note that Telegram is `platform = other`, `.docs/status/scraper.md` (blocker "first social platform" closed), run docs-check, add the `iw-ai-log` row, and run `pip-audit` if a dependency changed (none is planned)
- [ ] 4.2 Run the `iw-pr-review` skill and fix real findings; `iw-reviewer` reports no open blocking findings

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
