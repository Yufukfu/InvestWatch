---
when: Sat ~22:15
who: Kacper
---

## What was done with AI

Claude Code planned and applied `realtime-alerts` (Socket.IO client, cache updates, high-risk toasts) stacked on `findings-explorer`, with a fake socket through `vi.mock` in the tests and a live run in headless Chrome against a second mock container (`MOCK_CORS_ORIGINS='*'`)

## Outcome / lesson

jsdom tests all passed, but the browser run found the toast title rendering near-white on white: the toast region inherits the header's text colour, and CSS is not loaded in jsdom. The first live run also got 403 on the WebSocket, because the mock checks Origin and the dev port was not listed; this is now documented in `web/README.md` and ADR 0208. Mutation checks found two survivors (a high-risk payload without an id, an empty meta span)
