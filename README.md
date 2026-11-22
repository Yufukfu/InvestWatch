# InvestWatch

Monitoring of online investment promotion for UKNF (HackNation 2026): a scraping engine, three analytics modules (M1–M3) and a web dashboard.

## Repository structure

| Folder | Purpose |
|---|---|
| [`scraper/`](scraper/) | data collection: collectors, job queue, scheduler |
| [`analytics/`](analytics/) | preprocessing, modules M1–M3, LLM |
| [`api/`](api/) | database schema (Alembic), REST API, Socket.IO gateway |
| [`web/`](web/) | dashboard |
| [`infra/`](infra/) | shared infrastructure: Postgres, Redis, object storage (MinIO), optional Ollama, HTTPS gateway |
| [`contracts/`](contracts/) | data contracts (JSON Schema, OpenAPI 1.3.0), mocks, validator |
| [`.docs/`](.docs/) | project documentation (English): plans, decisions, AI work log |
| [`doc/`](doc/) | UKNF challenge materials (Polish), committed in the repository |

Who owns which folder: [`.github/CODEOWNERS`](.github/CODEOWNERS). Plans, decisions and the AI-assisted development log: [`.docs/`](.docs/INDEX.md), [AI log](.docs/ai-workflow.md).

## Quick Start

Requires Docker with Compose v2.20+.

```bash
./scripts/init-env.sh                # creates .env with random secrets (never committed)
docker compose up --build            # the whole stack; the first run also scans the seeded sources
# Local open model (Gemma via Ollama, several GB) instead of the hosted one:
./scripts/init-env.sh --local-llm && docker compose --profile llm up --build
```

Open https://localhost:8443 (local certificate: [`infra/README.md`](infra/README.md)). Scans, analysis and findings take a few minutes; check progress with the `bootstrap status` command in [`scraper/README.md`](scraper/README.md); `docker compose down -v` gives a clean start.

The LLM is optional: without one the system runs on rules only. The default is a hosted DeepSeek Flash through an OpenAI-compatible API ([ADR 0318](.docs/decisions/0318-hosted-llm-deepseek-flash.md); set `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` in `.env`), a mentor-approved exception to the on-premise rule that swaps to local Ollama by environment only ([ADR 0304](.docs/decisions/0304-llm-serving.md)).

## Hardware requirements

x86-64 or arm64 host with Docker. No GPU: compose declares no GPU device, so Ollama runs on CPU.

| | Default stack | With `--profile llm` |
|---|---|---|
| RAM for Docker, minimum | 6 GB | 12 GB |
| RAM for Docker, recommended | 8 GB | 16 GB |
| CPU cores, minimum / recommended | 4 / 8 | 6 / 12 |
| Free disk, minimum | 10 GB | 22 GB |

Limits, image sizes and model sizes behind these numbers, and how they were obtained: [`infra/README.md`](infra/README.md), "Resource sizing" (origin/main `ba32bd27`, 2026-11-22). Minimum = compose memory limits plus about 1.5 GB for the OS.

## Configuration

All settings are environment variables in the root `.env` (template: [`.env.example`](.env.example); secrets come from `./scripts/init-env.sh`). The per-service reference, with every variable and its default, is in [`infra/README.md`](infra/README.md#configuration-reference); module details are in the [`scraper`](scraper/README.md), [`analytics`](analytics/README.md), [`api`](api/README.md) and [`web`](web/README.md) READMEs.

## Licences of third-party services

All run unmodified, each as its own container; InvestWatch code links to none of them.

- **PostgreSQL 17**: PostgreSQL Licence (permissive). [postgresql.org/about/licence](https://www.postgresql.org/about/licence/)
- **Caddy 2** (gateway): Apache-2.0. [github.com/caddyserver/caddy](https://github.com/caddyserver/caddy/blob/master/LICENSE)
- **Redis 8**: used under its AGPLv3 option (also offered under RSALv2 and SSPLv1). [redis.io/legal/licenses](https://redis.io/legal/licenses/)
- **MinIO** (object storage): AGPL-3.0-or-later, built from source by Chainguard because upstream stopped publishing images ([ADR 0306](.docs/decisions/0306-object-storage-image.md)). [github.com/chainguard-forks/minio](https://github.com/chainguard-forks/minio)
- **Ollama** (optional `llm` profile): MIT. [github.com/ollama/ollama](https://github.com/ollama/ollama/blob/main/LICENSE). The `gemma3:4b` weights it downloads are under the Gemma Terms of Use, not an OSI licence. [ai.google.dev/gemma/terms](https://ai.google.dev/gemma/terms)

Each module owns its `compose.yaml`; the root [`compose.yaml`](compose.yaml) only includes them. A new module adds its file to that list.
