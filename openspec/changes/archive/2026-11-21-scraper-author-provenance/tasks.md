# Tasks

## 1. Drop the page-supplied author

- [x] 1.1 Failing test, then `build_document` dropping `author` from the page; the page-supplies-an-author scenario passes and the page dict is still not mutated
- [x] 1.2 Mutation check; `mutations: 2 tried, 2 caught` (empty untrusted set, filter not applied)

- [x] 1.3 Review fix: failing test, then the explicit `author=` argument through `build_document` and `Ingestor.ingest`; the collector-passes-account-data scenario passes; `mutations: 1 tried, 1 caught` (argument ignored)
- [x] 1.4 Review fix: pipeline test on real PostgreSQL, MinIO and Redis that the stored `documents.payload.author` is the collector's and a page-supplied one is not stored; `mutations: 2 tried, 2 caught` (`author=author` dropped from the `build_document` call, `author` not filtered from the page)

## 2. Closing

- [x] 2.1 Apply the `iw-docs-update` skill (`scraper/README.md`, `scraper/CLAUDE.md`, `.docs/integration-plan.md` §3 note, your domain file in `.docs/status/`), run docs-check, add the `iw-ai-log` row
- [x] 2.2 Run the `iw-pr-review` skill (security focus) and fix real findings

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
