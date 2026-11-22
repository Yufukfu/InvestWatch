---
when: Sat ~22:00
who: Adam
---

## What was done with AI

Had Claude Code resolve issue #31 (scraper NFC vs analytics NFKC `content_hash`) autonomously in a worktree: read both normalisers and every consumer of the value before choosing, then wrote the definition into integration-plan §3 and ADR 0105 and pinned it in the scraper with literal-hash tests

## Outcome / lesson

The scraper already followed the definition, so the new tests were green at once; the red proof is a scripted mutation check (6 mutants, 6 caught, the NFKC one failing exactly the compatibility-character cases). Evidence that mattered: nothing in analytics reads the hash yet, and NFKC would merge `10²` and `102` into one deduplicated row, which drops a real document. The hook asked for an active OpenSpec change even for a test-only commit, so a small change was proposed instead of using `IW_SKIP_SPEC`. Analytics (Damian) was not edited; its change is proposed in the issue
