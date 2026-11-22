---
when: Sun 02:30
who: Damian
---

## What was done with AI

Asked by the coordinator, the `analytics-embeddings` Claude Code session traced `main`'s red `test_redos` to #93. It timed `analyze` on exported trees from before #93, at #93 and after #81, then profiled it. It made the M2 rule passes cheaper without changing what they return, and proved that with a byte-for-byte comparison of rule results over the mocks, the gold set, hostile documents and 300 random documents.

## Outcome / lesson

Branch `analytics/m2-p1-hostile-input-perf`: 4.0 → 1.95 CPU s, with the test budget unchanged. The profile, not a guess, found the cost: the shared past-performance detector ran 3x per document, and R11 and R16 re-blanked their exclusions. The agent's first identity cache leaked one entry per sentence (R16 built a new list per call); a profile line caught it, and the list is now built once and the cache is bounded. The reviewer reran an independent differential check over 280,000 comparisons with 0 differences and pointed out conditional group references, now a fallback as well.
