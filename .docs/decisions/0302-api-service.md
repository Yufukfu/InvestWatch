# 0302. Placement and stack of the REST/WebSocket API

- Status: proposed
- Date: 2026-11-21
- Deciders: A, B, C (to be confirmed)

## Context

The dashboard needs the REST API in [`contracts/openapi.yaml`](../../contracts/openapi.yaml) and real-time events over Socket.IO ([integration-plan.md](../integration-plan.md) §5-§6). The team sync agreed that **C builds the API**, but B's layout has no `api/` directory ([STATUS.md](../STATUS.md)), and the root `CLAUDE.md` asks to confirm new directories with B. The API is on the critical path for Integration #1: until it exists, `web/` runs on mocks.

Constraints from the UKNF task (`doc/Opis Wyzwania HackNation UKNF 19.11.pdf`): modular architecture of lightweight services with frontend, backend and AI engine separated; backend in .NET/Python/Node.js; Socket.io named as the example for real-time alerts; architecture is 20% of the score.

## Options considered

1. **Separate `api/` service in Python (FastAPI + python-socketio), owner C.** Matches the integration plan and the "separate services" requirement. Same language as analytics, so the Pydantic models of the contracts can be shared or generated once. Adds a directory (needs B's OK and a `CLAUDE.md` in `api/`) and one more container.
2. **API inside the `analytics/` service.** One Python process serves REST/WS and runs the stream consumer. Fewer moving parts and no new directory. Mixes the AI engine and the backend in one service, which the task explicitly asks to separate, and a slow LLM call can stall API responses unless the consumer runs as a separate process of the same image.
3. **API as the backend of `web/` in Node.js/TypeScript (for example Express or NestJS + socket.io), owner B.** Socket.IO is native there and types can be generated from `openapi.yaml` for both sides. Moves work to B, whose load is the dashboard itself, and the database access logic would live in a second language next to the Python services.

## Decision

_To be written by the team (A, B, C)._

## Consequences

_To be written together with the decision._
