# Proposal

## Why

Issue #66. The requirement "Audited supply chain" of `scraper-deployment` says the `pip-audit` result is recorded in `.docs/security-audit.md`, and its scenario asks for a dated row there on every change. [ADR 0209](../../../.docs/decisions/0209-supply-chain-scanning.md) decision 2 replaced that team rule: per-PR scan results go in the PR body's "Security scans" section, because one shared row per PR made every PR conflict. `.docs/security-audit.md` keeps service notes, the hand-in run and long-lived residual risks. The spec still states the old rule.

## What Changes

- MODIFIED requirement "Audited supply chain" (capability `scraper-deployment`): the `pip-audit` result for `scraper/requirements*.txt` goes in the PR body's "Security scans" section with no unresolved finding; the scraper container section in `.docs/security-audit.md` stays and its claims match `scraper/compose.yaml`.
- No doc or code edit. The claims of the scraper container section in `.docs/security-audit.md` were checked against `scraper/compose.yaml` and the Dockerfile on `origin/main` and all match. `iw-pr-review`, `.docs/supply-chain.md`, `.docs/STATUS.md` and the security-audit header already follow ADR 0209, and no other doc or skill tells agents to add a dated `pip-audit` row (`iw-scraper-conventions` says only "`pip-audit` before merge; pin versions").

## Out of scope

- Existing dated rows in `.docs/security-audit.md` (kept as history by its header).
- CI enforcement of the scans (ADR 0209 follow-up).
- Any contract, REST route or event: this change touches none. Module owner: `scraper/` (Adam).

## Impact

- `openspec/specs/scraper-deployment/spec.md`, written by the archive of this change.
- Expected merge conflicts: PR #67 (`scraper/scraper-v3-render`) edits `.docs/security-audit.md` and `scraper/compose.yaml` but not `scraper-deployment`; this change edits neither file, so no textual conflict is expected.
