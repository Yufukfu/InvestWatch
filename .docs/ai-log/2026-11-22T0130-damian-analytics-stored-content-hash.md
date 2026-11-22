---
when: Sun ~01:30
who: Damian
---

## What was done with AI

A Claude Code side session, started by the analytics coordinator, implemented Damian's decision on issue #31 as `analytics-stored-content-hash`: remove analytics' own NFKC `content_hash` from `preprocess()` so it uses the scraper's stored NFC value (ADR 0105); test first and a backup-and-restore mutation check per task group

## Outcome / lesson

The brief said nothing read the hash, true on the old base; after moving onto the newer `main` the merged LLM cache key (ADR 0309) read it, so the change grew a second group: key on the stored hash, and bypass the cache for a document without one rather than compute a hash or share a `None` key. OpenSpec 2.1.1 refuses a MODIFIED block that drops a scenario, so "Equivalent texts hash the same" kept its name and was restated. The agent lost an hour to its own stray `cat >` waiting on stdin in a background command; scripts now run with stdin closed. Human merges
