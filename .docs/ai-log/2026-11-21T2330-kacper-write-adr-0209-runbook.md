---
when: Sat ~23:30
who: Kacper
---

## What was done with AI

Had Claude Code write ADR 0209 and the runbook `.docs/supply-chain.md` for the "verifiable supply chain" requirement: it read what CI, the hook and `init-env.sh` already do, checked Snyk's account and free-plan limits and the March 2026 Trivy tag compromise, and ran Gitleaks on the full history of `origin/main` (commit count not reproduced, see `security-audit.md`) instead of choosing from memory

## Outcome / lesson

Gitleaks first scanned 0 commits because a git worktree's `.git` points at the main checkout, which was not mounted; a "no leaks" result from that run would have been false. Its 2 real-run findings were mock ids, so the ADR requires an allowlist before Gitleaks can gate anything. OSV-Scanner never finished on the 8 GB MacBook Air: the file walk took under 1 s, then it stalled after loading the npm database, and a second copy started by the reviewer agent at the same time used up the laptop's CPU and RAM. It is not verified here and has no row in the audit log; the runbook sends it to CI. `iw-reviewer` (security focus) found 9 issues, all checked against the code and fixed: a high/critical gate that `pip-audit` and OSV-Scanner cannot apply (no severity threshold), a worktree history scan that reports a false clean, an overstated image-pinning claim, a pre-commit Gitleaks run that would read the untracked `.env`, and checklists that did not name the new scans. Lesson: ask about the machine before pulling large scanner images, and tell review agents not to run Docker
