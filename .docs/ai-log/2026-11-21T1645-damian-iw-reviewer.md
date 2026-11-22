---
when: Sat 16:45
who: Damian
---

## What was done with AI

Claude Code reviewed PR #8 (mock server), then fixed its own findings and the reviews from Adam and Kacper, test-first with a mutation check per group and the `iw-reviewer` agent on the fix commits

## Outcome / lesson

Two of the agent's ten findings were wrong (Socket.IO `*` origin, shutdown tasks): it had read a truncated library snippet, and corrected the PR comments once the full source showed it. The human reviews caught what the agent review missed: CI skipping the mock, `/__mock/*` reachable from any page, Socket.IO behind the gateway
