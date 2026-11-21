# InvestWatch

Monitoring of online investment promotion for UKNF (HackNation 2026): a scraping engine, three analytics modules (M1–M3) and a web dashboard.

## Repository structure

| Folder | Purpose | Owner |
|---|---|---|
| [`scraper/`](scraper/) | data collection: collectors, job queue, scheduler | A |
| [`analytics/`](analytics/) | preprocessing, modules M1–M3, LLM | C |
| [`web/`](web/) | dashboard | B |
| [`infra/`](infra/) | shared infrastructure: Postgres, HTTPS gateway | B |
| [`contracts/`](contracts/) | data contracts (JSON Schema, OpenAPI), mocks, validator – draft v1 | C |
| [`.docs/`](.docs/) | project documentation (English): plans, decisions, AI work log | all |
| [`doc/`](doc/) | UKNF challenge materials (Polish), removed before hand-in | – |

## Documentation

- [Integration plan](.docs/integration-plan.md) and [analytics plan](.docs/analytics-plan.md): drafts, contracts not yet confirmed
- [AI-assisted development log](.docs/ai-workflow.md)

## Quick Start

Requires Docker with Compose v2.20+.

```bash
./scripts/init-env.sh          # creates .env with random secrets (never committed)
docker compose up --build      # postgres, redis, minio (bucket iw-raw), gateway, web
docker compose --profile llm up -d   # optional: local Gemma (gemma3:4b via Ollama, several GB download)
```

The LLM is a hosted OpenAI-compatible model by default (a mentor-approved exception to the on-premise rule, [ADR 0304](.docs/decisions/0304-llm-serving.md)); the `llm` profile is the local open-model fallback. Infrastructure, networks and the joining contract for new modules: [`infra/README.md`](infra/README.md).

Open https://localhost:8443 (local certificate: see [`infra/README.md`](infra/README.md)). Until `api` exists the dashboard shows "Brak połączenia z API"; for UI work without it, run `web/` in mock mode ([`web/README.md`](web/README.md)).

Each module owns its `compose.yaml`; the root [`compose.yaml`](compose.yaml) only includes them. A new module adds its file to that list.
