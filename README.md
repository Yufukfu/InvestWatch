# InvestWatch

Monitoring of online investment promotion for UKNF (HackNation 2026): a scraping engine, three analytics modules (M1–M3) and a web dashboard.

## Repository structure

| Folder | Purpose | Owner |
|---|---|---|
| [`scraper/`](scraper/) | data collection: collectors, job queue, scheduler | Adam |
| [`analytics/`](analytics/) | preprocessing, modules M1–M3, LLM | Damian |
| [`web/`](web/) | dashboard | Kacper |
| [`infra/`](infra/) | shared infrastructure: Postgres, HTTPS gateway | Kacper |
| [`contracts/`](contracts/) | data contracts (JSON Schema, OpenAPI), mocks, validator – draft v1 | Damian |
| [`.docs/`](.docs/) | project documentation (English): plans, decisions, AI work log | all |
| [`doc/`](doc/) | UKNF challenge materials (Polish), removed before hand-in | – |

## Documentation

- [Integration plan](.docs/integration-plan.md) and [analytics plan](.docs/analytics-plan.md): drafts, contracts not yet confirmed
- [AI-assisted development log](.docs/ai-workflow.md)

## Quick Start

Requires Docker with Compose v2.20+.

```bash
./scripts/init-env.sh          # creates .env with random passwords (never committed)
docker compose up --build      # postgres, gateway, web
```

Open https://localhost:8443 (local certificate: see [`infra/README.md`](infra/README.md)). Until `api` exists the dashboard shows "Brak połączenia z API"; for UI work without it, run the contract mock server and point `API_UPSTREAM` at it, or use `npm run dev` in `web/` against it ([`contracts/README.md`](contracts/README.md), "Mock server"; [`web/README.md`](web/README.md)).

Each module owns its `compose.yaml`; the root [`compose.yaml`](compose.yaml) only includes them. A new module adds its file to that list.
