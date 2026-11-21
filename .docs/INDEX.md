# Documentation index

"How do I…?" router: find your task, open only that file and section. Business logic lives in these docs and in `openspec/`, not in `CLAUDE.md` files. Docs are in English; user-facing dashboard texts are Polish.

## How do I…

| I want to… | Open |
|---|---|
| See where we are and what is blocked | [STATUS.md](STATUS.md) (milestones, team-wide), then your domain: [status/scraper.md](status/scraper.md), [status/dashboard.md](status/dashboard.md), [status/platform.md](status/platform.md) |
| Understand the architecture and how services connect | [integration-plan.md](integration-plan.md) §1-2 |
| Produce or consume a scraped document | [integration-plan.md](integration-plan.md) §3, then [../scraper/CLAUDE.md](../scraper/CLAUDE.md) |
| What exactly `content_hash` hashes (normalisation, who computes it) | [integration-plan.md](integration-plan.md) §3, [decisions/0105-content-hash-normalisation.md](decisions/0105-content-hash-normalisation.md) |
| Add or change a seeded source (`scraper/seeds/*.toml`, `python -m iw_scraper.seed`) | [../scraper/README.md](../scraper/README.md), [../scraper/CLAUDE.md](../scraper/CLAUDE.md) (`seed`) |
| Find new sources to look at (candidates from stored links, how a human approves one) | [../scraper/README.md](../scraper/README.md), [decisions/0108-source-discovery-candidates.md](decisions/0108-source-discovery-candidates.md) |
| Load saved samples (data from the stand, offline demo replay) through the normal ingest | [../scraper/README.md](../scraper/README.md) (Import saved samples) |
| Store, dedup and announce a document (DB, MinIO, `iw:documents`, republish sweep) | [../scraper/CLAUDE.md](../scraper/CLAUDE.md) (Ingest), [decisions/0104-ingest-order-and-republish-sweep.md](decisions/0104-ingest-order-and-republish-sweep.md) |
| Produce or consume a finding | [integration-plan.md](integration-plan.md) §4, then [../analytics/CLAUDE.md](../analytics/CLAUDE.md) |
| Run or operate the analytics worker (env, feeding a document, poison messages, `/health`, registry) | [../analytics/README.md](../analytics/README.md) "Run the worker" and "Configuration", then [../openspec/specs/document-stream-worker/spec.md](../openspec/specs/document-stream-worker/spec.md) |
| Refresh or check the KNF firm registry (`registry/knf.csv`, curated domains, ids) | [../analytics/registry/README.md](../analytics/registry/README.md), then [decisions/0311-knf-registry-source-and-ids.md](decisions/0311-knf-registry-source-and-ids.md) |
| Build or call the REST API | [integration-plan.md](integration-plan.md) §5 |
| Know what the API does beyond the contract (risk level, filters, calibration, Socket.IO relay, limits) | [../api/README.md](../api/README.md) "REST and Socket.IO", then [../openspec/specs/rest-api/spec.md](../openspec/specs/rest-api/spec.md) and [../openspec/specs/event-relay/spec.md](../openspec/specs/event-relay/spec.md) |
| Read or write the shared tables, or add a migration | [../api/README.md](../api/README.md) (tables and the exact SQL for writers), then [../api/CLAUDE.md](../api/CLAUDE.md) |
| Run the stack, add a module to compose, connect to the database | [../infra/README.md](../infra/README.md), then [../infra/CLAUDE.md](../infra/CLAUDE.md) |
| Handle real-time events and alerts | [integration-plan.md](integration-plan.md) §6, then [../web/CLAUDE.md](../web/CLAUDE.md) |
| Follow shared conventions (env vars, logs, migrations, branches) | [integration-plan.md](integration-plan.md) §7 |
| Check milestones and deadlines | [integration-plan.md](integration-plan.md) §8 |
| Work on the analytics pipeline, rules R1-R18, LLM layer or calibration | [analytics-plan.md](analytics-plan.md) §2, §5, §7, §8 |
| Know which module a document goes to, or change the M1/M3 signals (S1.x, S3.x) | [../analytics/README.md](../analytics/README.md) "Modules and routing", then [../openspec/specs/m1-third-party-signals/spec.md](../openspec/specs/m1-third-party-signals/spec.md), [../openspec/specs/m3-unauthorized-advice-signals/spec.md](../openspec/specs/m3-unauthorized-advice-signals/spec.md) and [decisions/0308-m3-s34-gate.md](decisions/0308-m3-s34-gate.md) |
| Add or relabel a gold-set document, run the evaluation | [../analytics/eval/README.md](../analytics/eval/README.md), then [../analytics/README.md](../analytics/README.md) "Gold-set evaluation" |
| Read the UKNF challenge and the 18 rules | the Polish materials in [../doc/](../doc/) (read-only, removed before hand-in) |
| Use or change a contract (a change needs the whole team and a version bump) | [../contracts/README.md](../contracts/README.md), [../contracts/CLAUDE.md](../contracts/CLAUDE.md), [integration-plan.md](integration-plan.md) §3-§6 |
| Find out why we chose X, or record a decision | [decisions/README.md](decisions/README.md) |
| See what the system does now, or what is in flight | [../openspec/specs/](../openspec/specs/), [../openspec/changes/](../openspec/changes/) |
| Start a task, or know the process and review bar | [../.claude/SDLC.md](../.claude/SDLC.md), [../.claude/CODE_REVIEW.md](../.claude/CODE_REVIEW.md) |
| Update docs after a change | [../.claude/skills/iw-docs-update/SKILL.md](../.claude/skills/iw-docs-update/SKILL.md) |
| Log AI usage for the jury | [ai-workflow.md](ai-workflow.md) |

## Rules

- Don't duplicate. Link to the owning file and section.
- A doc claim that matters gets checked against the code before it is relied on.
- A new service directory gets its own `CLAUDE.md`, a row in the root [`CLAUDE.md`](../CLAUDE.md) services table and a row here.
- `node .claude/skills/iw-docs-update/scripts/docs-check.mjs` checks paths, the ADR index and service `CLAUDE.md` files.
