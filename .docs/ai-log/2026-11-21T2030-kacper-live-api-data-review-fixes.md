---
when: Sat ~20:30
who: Kacper
---

## What was done with AI

Had Claude Code address Adam's request-changes review of PR #25: read the review first, reproduced both guard-test bypasses in a scratch copy before widening the test (all shipped files, imports from `src/test/`, `msw/browser`), made the default test trend handler fail for `bucket=day`, and recorded the demo consequence (compose has no REST backend; mock server run by hand) in ADR 0206, status and the web README in a follow-up change `live-api-data-review-fixes`

## Outcome / lesson

An earlier draft reply to Adam was written without reading his review and had to be redone: read the PR comments before answering. A MODIFIED spec block cannot rename scenarios, so two scenario titles and the Purpose were edited by hand (no behaviour change)
