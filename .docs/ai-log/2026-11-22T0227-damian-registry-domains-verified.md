---
when: Sun 02:27
who: Damian
---

## What was done with AI

Damian checked by hand all 31 curated domains that an agent had drafted for `analytics/registry/knf_domains_manual.csv` (each row's `source_url` against the firm's name). The analytics coordinating Claude Code session then flipped every `verified_by_human` to `true` and set `curated_unverified` to 0 in `knf.meta.json`, without re-running the live KNF loader. It also updated the registry README and the platform status.

## Outcome / lesson

Docs and data only. The registry tests and `docs-check` passed before the PR. The agent drafts and a human confirms: the flag records which rows a person looked at, so a new curated row still starts as `false`.
