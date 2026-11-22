# Tasks

## 1. Include path

- [x] 1.1 Failing test first: a `root`-group scenario in `scraper/tests/stack.sh` that merges the documented `-f` chain and checks `renderer`; watch it fail on the bare include
- [x] 1.2 `scraper/compose.yaml` includes `../scraper/compose.renderer.yaml`; every chain in the issue passes `docker compose config -q`
- [x] 1.3 Mutation check: revert the include to the bare name, the scenario goes red (`mutations: 1 tried, 1 caught`)

## 2. Closing

- [x] 2.1 Apply the iw-docs-update skill (`docs-check: ok`; `.docs/status/scraper.md` row) and add the iw-ai-log row
- [ ] 2.2 Run the iw-pr-review skill and fix real findings
