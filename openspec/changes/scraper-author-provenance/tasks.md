# Tasks

## 1. Drop the page-supplied author

- [x] 1.1 Failing test, then `build_document` dropping `author` from the page; the page-supplies-an-author scenario passes and the page dict is still not mutated
- [x] 1.2 Mutation check; `mutations: 2 tried, 2 caught` (empty untrusted set, filter not applied)

## 2. Closing

- [x] 2.1 Apply the `iw-docs-update` skill (`scraper/README.md`, `scraper/CLAUDE.md`, `.docs/integration-plan.md` §3 note, your domain file in `.docs/status/`), run docs-check, add the `iw-ai-log` row
- [ ] 2.2 Run the `iw-pr-review` skill (security focus) and fix real findings

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
