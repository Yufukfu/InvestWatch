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
./scripts/init-env.sh          # creates .env with random secrets (never committed)
docker compose up --build      # postgres, redis, minio (bucket iw-raw), gateway, web
docker compose --profile llm up -d   # optional: local Gemma (gemma3:4b via Ollama, several GB download)
```

The LLM is a hosted OpenAI-compatible model by default (a mentor-approved exception to the on-premise rule, [ADR 0304](.docs/decisions/0304-llm-serving.md)); the `llm` profile is the local open-model fallback. Infrastructure, networks and the joining contract for new modules: [`infra/README.md`](infra/README.md).

Open https://localhost:8443 (local certificate: see [`infra/README.md`](infra/README.md)). Until `api` exists the dashboard shows "Brak połączenia z API"; for UI work without it, run the contract mock server and point `API_UPSTREAM` at it, or use `npm run dev` in `web/` against it ([`contracts/README.md`](contracts/README.md), "Mock server"; [`web/README.md`](web/README.md)).

## Licences of third-party services

All run unmodified, each as its own container; InvestWatch code links to none of them.

- **PostgreSQL 17**: PostgreSQL Licence (permissive). [postgresql.org/about/licence](https://www.postgresql.org/about/licence/)
- **Caddy 2** (gateway): Apache-2.0. [github.com/caddyserver/caddy](https://github.com/caddyserver/caddy/blob/master/LICENSE)
- **Redis 8**: used under its AGPLv3 option (also offered under RSALv2 and SSPLv1). [redis.io/legal/licenses](https://redis.io/legal/licenses/)
- **MinIO** (object storage): AGPL-3.0-or-later, built from source by Chainguard because upstream stopped publishing images ([ADR 0306](.docs/decisions/0306-object-storage-image.md)). [github.com/chainguard-forks/minio](https://github.com/chainguard-forks/minio)
- **Ollama** (optional `llm` profile): MIT. [github.com/ollama/ollama](https://github.com/ollama/ollama/blob/main/LICENSE). The `gemma3:4b` weights it downloads are under the Gemma Terms of Use, not an OSI licence. [ai.google.dev/gemma/terms](https://ai.google.dev/gemma/terms)

Each module owns its `compose.yaml`; the root [`compose.yaml`](compose.yaml) only includes them. A new module adds its file to that list.
