# 0302. Placement and stack of the REST/WebSocket API

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written from Damian's choices; accepted by Adam, Kacper and Damian via PR #3

## Context

The dashboard needs the REST API in [`contracts/openapi.yaml`](../../contracts/openapi.yaml) and real-time events over Socket.IO ([integration-plan.md](../integration-plan.md) §5-§6). The team sync agreed that **Damian builds the API**, but Kacper's layout has no `api/` directory ([STATUS.md](../STATUS.md)), and the root `CLAUDE.md` asks to confirm new directories with Kacper. The API is on the critical path for Integration #1: until it exists, `web/` runs on mocks.

Constraints from the UKNF task (`doc/Opis Wyzwania HackNation UKNF 19.11.pdf`): modular architecture of lightweight services with frontend, backend and AI engine separated; backend in .NET/Python/Node.js; Socket.io named as the example for real-time alerts; architecture is 20% of the score.

## Options considered

1. **Separate `api/` service in Python (FastAPI + python-socketio), owner Damian.** Matches the integration plan and the "separate services" requirement. Same language as analytics, so the Pydantic models of the contracts can be shared or generated once. Adds a directory (needs Kacper's OK and a `CLAUDE.md` in `api/`) and one more container.
2. **API inside the `analytics/` service.** One Python process serves REST/WS and runs the stream consumer. Fewer moving parts and no new directory. Mixes the AI engine and the backend in one service, which the task explicitly asks to separate, and a slow LLM call can stall API responses unless the consumer runs as a separate process of the same image.
3. **API as the backend of `web/` in Node.js/TypeScript (for example Express or NestJS + socket.io), owner Kacper.** Socket.IO is native there and types can be generated from `openapi.yaml` for both sides. Moves work to Kacper, whose load is the dashboard itself, and the database access logic would live in a second language next to the Python services.

## Decision

Option 1: **a separate `api/` service in Python (FastAPI + python-socketio), owned by Damian.**

Why (Damian):
- The UKNF task explicitly asks for frontend, backend and AI engine as separate services, and architecture is 20% of the score; a dedicated `api/` service meets that most directly.
- Slow LLM calls in analytics cannot stall REST/WebSocket responses, because the API runs in its own process and container.

## Consequences

- Matches the integration plan and the task's "separate services" requirement; analytics stays an AI engine only.
- The Pydantic models of the contracts can be shared with analytics or generated once from the schemas.
- Needs Kacper's OK for the new top-level `api/` directory, a `CLAUDE.md` inside `api/`, and `api` added to `SERVICE_DIRS` in `.claude/skills/iw-docs-update/scripts/docs-check.mjs`; [STATUS.md](../STATUS.md) blocker about the missing `api/` closes.
- One more container in `docker compose`; `web/` stays on mocks until the API serves the first endpoints, so it remains on the critical path for Integration #1.
