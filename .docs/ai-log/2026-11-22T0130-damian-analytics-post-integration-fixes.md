---
when: Sun ~01:30
who: Damian
---

## What was done with AI

A Claude Code side session (from the coordinator) applied `analytics-post-integration-fixes` from the defects of two end-to-end runs on real data. It worked test-first in three groups, each with a scripted mutation check and a subagent review. The changes: the KNF warnings page is no longer an M1 advertiser (`official_source`); EY's family-office page no longer gives M3 0.269 from vocabulary alone (an offer signal is required); preprocessing runs NFKC once. It then re-ran the gold set with hosted Gemma 4

## Outcome / lesson

Group 1's review caught two real defects: a bad env value failed every document instead of stopping startup, and `www.` entries never matched. Three mutants were first killed by an unpack error, which does not count as a red, so the test was tightened. The ratio-based growth test cannot see a tiny quadratic term, and the session recorded that instead of hiding it. The LLM run was not a measurement: 503s, plus 11 HTTP-200 answers that were not a JSON object. The numbers went to Damian, and the defaults are unchanged
