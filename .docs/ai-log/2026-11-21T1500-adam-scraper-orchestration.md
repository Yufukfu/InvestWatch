---
when: Sat pm
who: Adam
---

## What was done with AI

Ran stream C of the scraper split (`scraper-orchestration`) with Claude Code in a worktree: spiked `arq` against a real Redis first (duplicate job id, resume after SIGKILL), then per task group a failing test, the code, a scripted mutation check (backup, mutate, scoped run, restore) and a fresh `iw-reviewer`; every finding verified against the code before a follow-up commit

## Outcome / lesson

Branch `scraper/scraper-orchestration`, PR pending. The reviewers found real bugs the author and the mutation runs missed (`scan.finished` lost when the status write failed, a scheduler slot lost after a failed tick, non-UTF8 field blocking the consumer, a log path that could print proxy credentials); mutation runs found untested guards instead (lease renewal, first-tick catch-up) and one survivor no test can observe. The agent got wrong: the handover note's `git rebase 73333cb` replayed 12 unrelated commits (conflicts exposed it, `rebase --onto` fixed it), and several of its own tests (a regex rename that shadowed a variable, unbounded polling loops that hung instead of failing, a Python 3.12 `wait_for` deadlock in a proxy fixture). `pip-audit` flagged the old `pytest` pin; the bump was tested before keeping it. After the `scraper-v1` and `scraper-ingest` PRs merged, the agent merged `main`, found that `arq 0.28.0` needs `redis<6` while `main` pinned `redis 8.1.0`, that `DomainGate` duplicated the queue's domain state, and that `sources.documents_count` has no column; the end-to-end tests (real Redis 8, PostgreSQL, MinIO) and a security review of the collector (unbounded `Retry-After`) caught what the stubbed tests could not
