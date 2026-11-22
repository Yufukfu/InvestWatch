---
when: Sat ~22:00
who: Damian
---

## What was done with AI

Had Claude Code (a side session of the analytics coordinator) plan and implement `analytics-knf-registry`: fetch the five KNF pages read-only and record the evidence, then six task groups test-first with saved snapshots (no network in tests), a mutation check and an `iw-reviewer` subagent per group, a live run that committed the real register (749 firms), curated domains for 31 Polish firms checked against their homepages (`verified_by_human=false`), and R1 on the official name

## Outcome / lesson

Reviewers caught real bugs in every group: redirects to any host, a carried id lost on the second reload, `find_name` failing R1 on a firm chosen by domain, curated domains silently taking another firm's domain, common words (`LONDON`, `AND`) as 0.95 aliases in the committed data. The snapshot itself showed the planned "drop short aliases" rule would drop XTB, mBank and Pekao; the plan was changed to a case guard. Matching 1,000 firms went from 5.5 s to 0.3 s per document. The local OpenSpec 1.2.0 again missed the 2.1.1 500-character rule; the specs were refitted after rebasing on `main`
