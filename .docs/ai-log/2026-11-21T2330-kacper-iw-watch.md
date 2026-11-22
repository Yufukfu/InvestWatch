---
when: Sat ~23:30
who: Kacper
---

## What was done with AI

Had Claude Code build `iw-watch`, a watcher that lets our agents hand work to each other through GitHub (OpenSpec `agent-watch`): six task groups test-first with a mutation check each (162 mutants, all caught in the end), an `iw-reviewer` pass per group, then real `claude -p` probes and a live dry run on a real request-changes review (PR #39)

## Outcome / lesson

The design assumed `--max-turns`; the real `claude --help` (2.1.330) has none, so the cap is a budget plus a timeout. Three cheap probes with decoy files showed that project hooks run even in an untrusted clone (so checking out a PR to review it would run that PR's hooks: reviews now stay on the base branch) and that its project allow rules are ignored. The reviews found real bugs the tests had not: time cursors that lose inline comments, no pagination, unscoped file tools. The first live run failed on a stale commit-graph and left a clone that blocked later runs; both fixed and pinned
