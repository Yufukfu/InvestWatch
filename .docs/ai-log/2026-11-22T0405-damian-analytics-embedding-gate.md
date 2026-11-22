---
when: Sun ~04:00
who: Damian
---

## What was done with AI

Damian asked for embeddings in the topic gate ("wykorzystanie embeddingów w bramkowaniu wiadomości"). A coordinator session handed the task to a side session with a brief: rescue only, dictionary first, degrade without an embedder, budget inside `CLAIM_MIN_IDLE_MS`, calibrate on real `bge-m3`. The agent wrote the OpenSpec change (`analytics-embedding-gate`) and sent a 5-line design summary. It waited for Damian's "Akceptuję" before coding, then ran iw-commit-cycle per group: failing tests, mutation check, one `iw-reviewer` pass. Before the approval it probed a separate local `bge-m3` container, which showed that an absolute cosine threshold cannot separate Polish texts. That led to the on-topic minus off-topic margin.

## Outcome / lesson

- **Mutation checks found five weak tests.** Survivors in groups 1, 3 and 4 showed a missing seed-class case, a worker test that never reached the analysis, and a sweep boundary. Group 2's first draft lacked the stored-hash and failed-outcome asserts, which the mutation list exposed.
- **An order-dependent test.** One test passed alone but failed in the full suite, because a CLI test raises the root logger to INFO. The fix was `caplog.clear()`.
- **Agent slip: line endings.** Editing files with Python `open(..., "w")` on Windows wrote CRLF, so the mutation runner's snippets stopped matching. The fix was to normalize to LF and use `newline=""`.
- **Reviews.** Two `iw-reviewer` passes found no blocking findings. One note, a duplicate `no_centroids` log line, was fixed.
- **Coordinator catch (from Kacper's README PR #119).** `GATE_SIM_THRESHOLD` was forwarded by compose but never read. It is replaced by `GATE_EMBED_MIN_MARGIN`, and a test checks that every `GATE_*` setting is forwarded.
