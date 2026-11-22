---
when: Sat pm
who: Adam
---

## What was done with AI

Ran the first real `/openspec-propose scraper-v1`; read the installed noble-tls, curl_cffi, httpx and queue-library APIs in a scratch venv to draft ADR options; ported `test-diff-check` (extended for pytest) and a stale-checkout SessionStart hook, both test-first

## Outcome / lesson

Draft ADRs 0101-0103 leave the decision blank for a human. A test caught a wrong fixture of mine (a rename target under `tests/` still counts as a test file). The stale-checkout hook was live-checked on a scratch clone two commits behind. Whole-branch review is the closing step of this PR
