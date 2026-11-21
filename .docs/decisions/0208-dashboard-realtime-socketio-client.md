# 0208. Dashboard real-time client: socket.io-client

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by Kacper via the `realtime-alerts` PR

## Context

The dashboard must show alerts in real time ([`web/CLAUDE.md`](../../web/CLAUDE.md), "Done"). Events reach the browser over Socket.IO, namespace `/events` on path `/socket.io` ([integration-plan.md](../integration-plan.md) §6, [event-relay spec](../../openspec/specs/event-relay/spec.md)). Both servers the dashboard talks to are python-socketio `AsyncServer` instances: `api/src/investwatch_api/events.py` and `contracts/mock-server/src/iw_mock_server/events.py`. Both pin `python-socketio==5.18.1` (`api/requirements.txt`, `contracts/mock-server/requirements.txt`). Adding a browser dependency needs an ADR when it is a new choice ([`.claude/rules/web-dashboard.md`](../../.claude/rules/web-dashboard.md)). The layering rule already lists `socket.io-client` as a package that components may not import (`web/.oxlintrc.json`, [ADR 0204](0204-frontend-architecture.md)).

## Options considered

1. **`socket.io-client` 4.8.4** (MIT, published 2026-09-25). It speaks the Socket.IO v5 / Engine.IO v4 protocol that python-socketio 5.x serves (the handshake seen in the browser run is `/socket.io/?EIO=4`). Its direct dependencies are `engine.io-client`, `socket.io-parser`, `@socket.io/component-emitter` and `debug`. `engine.io-client` pulls in `engine.io-parser`, `ws` and `xmlhttprequest-ssl` (all in `web/package-lock.json`; the lock records MIT for `engine.io-parser` and `ws` and has no licence field for `xmlhttprequest-ssl`, to check at the next install). `npm audit` reported 0 vulnerabilities after the install. Measured with `vite build` in the PR #40 review: the main chunk grew from 107.2 to 121.67 kB gzip (an earlier build gave 121.5 kB); after the review fixes (round 3) it is 122.55 kB.
2. **The browser's own `WebSocket`.** No dependency, but it would have to implement the Engine.IO handshake, pings, the packet encoding and namespace join by hand. Against a server that expects those, that means reimplementing the client library, with its reconnection rules, inside `web/`.
3. **Server-Sent Events.** Simple in the browser, but the api and the mock server would need a new endpoint and a contract change, and contracts are frozen ([ADR 0301](0301-contracts-v1.md)).

## Decision

Option 1: `socket.io-client`. It is imported in one place only, `web/src/features/alerts/data/socket.ts`, and the app opens exactly one connection, owned by `useRealtime`.

Rationale: it is the protocol both servers already speak (python-socketio 5.18.1, with `EIO=4` observed in the live run against the mock). Option 2 would mean maintaining a protocol client. Option 3 needs a server and contract change. The cost is about 14.5 kB gzip, measured above.

## Consequences

- Reconnection and the fallback from WebSocket to HTTP long-polling come from the library. After every connect the dashboard refetches over REST, because Pub/Sub has no replay (event-relay spec).
- Tests never open a socket. They replace the module with `vi.mock('socket.io-client')` and drive a fake socket (`src/features/alerts/data/useRealtime.test.tsx`, `src/test/inertSocket.ts`).
- In development, the mock server checks the Origin header of WebSocket and polling requests against `MOCK_CORS_ORIGINS` (default `http://localhost:5173`, ...). A dev server on another port gets 403 unless that variable lists it or is `*` (`contracts/README.md`). Behind the gateway the origin is the same, so this does not apply.
- Replacing the client later is a new ADR that supersedes this one.
