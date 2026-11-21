# InvestWatch

Monitoring of online investment promotion for UKNF (HackNation 2026): a scraping engine, three analytics modules (M1–M3) and a web dashboard.

## Repository structure

| Folder | Purpose | Owner |
|---|---|---|
| [`scraper/`](scraper/) | data collection: collectors, job queue, scheduler | A |
| [`analytics/`](analytics/) | preprocessing, modules M1–M3, LLM | C |
| [`web/`](web/) | dashboard | B |
| [`doc/`](doc/) | UKNF materials, plans, ADRs, AI work log | all |

Decision: [ADR-0001](doc/adr/0001-repository-structure.md).

## Documentation

- [Integration plan](doc/integration-plan.md) and [analytics plan](doc/analytics-plan.md): drafts, contracts not yet confirmed
- [Architecture decision records](doc/adr/README.md): agreed decisions and the backlog of open ones
- [AI-assisted development log](doc/ai-workflow.md)

## Quick Start

Not available yet. It will be added together with the deployment ADR (docker compose, single-command start).
