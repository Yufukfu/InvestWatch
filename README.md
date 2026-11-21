# InvestWatch

Monitoring of online investment promotion for UKNF (HackNation 2026): a scraping engine, three analytics modules (M1–M3) and a web dashboard.

## Repository structure

| Folder | Purpose | Owner |
|---|---|---|
| [`scraper/`](scraper/) | data collection: collectors, job queue, scheduler | A |
| [`analytics/`](analytics/) | preprocessing, modules M1–M3, LLM | C |
| [`web/`](web/) | dashboard | B |
| [`contracts/`](contracts/) | data contracts (JSON Schema, OpenAPI), mocks, validator – draft v1 | C |
| [`.docs/`](.docs/) | project documentation (English): plans, decisions, AI work log | all |
| [`doc/`](doc/) | UKNF challenge materials (Polish), removed before hand-in | – |

## Documentation

- [Integration plan](.docs/integration-plan.md) and [analytics plan](.docs/analytics-plan.md): drafts, contracts not yet confirmed
- [AI-assisted development log](.docs/ai-workflow.md)

## Quick Start

Not available yet. It will be added together with the deployment ADR (docker compose, single-command start).
