---
when: Sat ~20:17
who: Damian
---

## What was done with AI

Had a Claude Code side session propose and apply `analytics-m1-m3` (rules-only M1/M3, routing by publisher and registry) while a coordinating session relayed Damian's product answers from the challenge documents (Art. 76, the KNF registers, the M1/M3 outputs). Per task group: failing test first, a scripted mutation check, one reviewer agent

## Outcome / lesson

Branch `analytics/analytics-m1-m3`, stacked on PR #26. The plan was rewritten twice: once to reuse `analytics-llm-p0`'s judge seam instead of a second protocol, once to the challenge criteria (firm accounts to M2, unregistered own pages to M3, S3.4 alone lifts the gate). Reviewers caught a URL backslash that let a scraped link pose as a firm, false S3.4 candidates (`akcja promocyjna`), attribution that saw only the first candidate and NaN weights. The mutation runner exposed a worker test that hung on Redis instead of failing. LLM wiring for M1/M3 deferred to a follow-up change
