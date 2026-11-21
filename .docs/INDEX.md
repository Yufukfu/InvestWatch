# Documentation index

"How do I…?" router: find your task, open only that file and section. Business logic lives in these docs and in `openspec/`, not in `CLAUDE.md` files. Docs are in English; user-facing dashboard texts are Polish.

## How do I…

| I want to… | Open |
|---|---|
| See where we are and what is blocked | [STATUS.md](STATUS.md) (milestones, team-wide), then your domain: [status/scraper.md](status/scraper.md), [status/dashboard.md](status/dashboard.md), [status/platform.md](status/platform.md) |
| Understand the architecture and how services connect | [integration-plan.md](integration-plan.md) §1-2 |
| Produce or consume a scraped document | [integration-plan.md](integration-plan.md) §3, then [../scraper/CLAUDE.md](../scraper/CLAUDE.md) |
| Produce or consume a finding | [integration-plan.md](integration-plan.md) §4, then [../analytics/CLAUDE.md](../analytics/CLAUDE.md) |
| Build or call the REST API | [integration-plan.md](integration-plan.md) §5 |
| Read or write the shared tables, or add a migration | [../api/README.md](../api/README.md) (tables and the exact SQL for writers), then [../api/CLAUDE.md](../api/CLAUDE.md) |
| Run the stack, add a module to compose, connect to the database | [../infra/README.md](../infra/README.md), then [../infra/CLAUDE.md](../infra/CLAUDE.md) |
| Handle real-time events and alerts | [integration-plan.md](integration-plan.md) §6, then [../web/CLAUDE.md](../web/CLAUDE.md) |
| Follow shared conventions (env vars, logs, migrations, branches) | [integration-plan.md](integration-plan.md) §7 |
| Check milestones and deadlines | [integration-plan.md](integration-plan.md) §8 |
| Work on the analytics pipeline, rules R1-R18, LLM layer or calibration | [analytics-plan.md](analytics-plan.md) §2, §5, §7, §8 |
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
