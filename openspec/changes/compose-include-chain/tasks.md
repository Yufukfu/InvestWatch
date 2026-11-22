# Tasks

## 1. Include path

- [ ] 1.1 Failing test first: a `config` scenario in `scraper/tests/stack.sh` that merges the documented `-f` chain and checks `renderer`; watch it fail on the bare include
- [ ] 1.2 `scraper/compose.yaml` includes `../scraper/compose.renderer.yaml`; every chain in the issue passes `docker compose config -q`
- [ ] 1.3 Mutation check: revert the include to the bare name, the scenario goes red (`mutations: N tried, N caught`)

## 2. Closing

- [ ] 2.1 Apply the iw-docs-update skill (`docs-check: ok`; `.docs/status/scraper.md` row) and add the iw-ai-log row
- [ ] 2.2 Run the iw-pr-review skill and fix real findings
