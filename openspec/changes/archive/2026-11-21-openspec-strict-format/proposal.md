# Proposal

## Why

The CI job `Specs and hooks` (added in PR #24) runs `npx -y @fission-ai/openspec@2.1.1 validate --all --strict`. In strict mode a warning fails the run, and OpenSpec 2.1.1 warns when a requirement's text before its first scenario is longer than 500 characters. Five specs on `main` (`database-schema`, `document-analysis`, `m2-compliance-rules`, `rest-api`, `shared-infrastructure`) fail it with 14 such requirements, so the job is red for everyone (run 44938364002; `rest-api` joined the list once PR #28 merged). OpenSpec 1.2.0, which some of us still had installed, has no such check, so this went unnoticed locally.

## What Changes

- Each of the 14 requirements keeps its header, its main SHALL statements and every scenario it already has. The sentences that pushed it over 500 characters move into the scenarios of the same requirement, word for word where possible: as an `**AND**` line on the existing scenario that already tests that rule, or as a new scenario where none did (4 new: `Firm name without word tokens`, `Unreadable input or bad configuration`, `Metric formulas`, `Only the pull reaches the internet`).
- No requirement is renamed, split, added or removed, and no scenario is renamed or removed. No behaviour, contract, REST route or event changes; no code changes.
- `Rule catalogue`, `R3 risk information next to return claims` and `M2 finding assembly` are also MODIFIED by the in-flight changes `analytics-llm-p0` and `analytics-m1-m3`. For these three, text moves only into scenarios that already exist, so those changes do not have to copy new scenario names into their MODIFIED blocks.

**Out of scope:** the in-flight changes `analytics-llm-p0` and `analytics-m1-m3` fail the same 2.1.1 check in their own deltas, and `analytics-m1-m3` also omits existing scenarios from two MODIFIED blocks. They are fixed on their own branches (see `follow-ups.md`). Owner Damian.

## Capabilities

### Modified Capabilities
- `database-schema`: `Columns follow the contracts`.
- `document-analysis`: `Firm registry matching`, `M2 finding assembly`, `Command-line batch`.
- `m2-compliance-rules`: `Rule catalogue`, `R2 ad labeling`, `R3 risk information next to return claims`.
- `rest-api`: `Findings list filters, sort and pagination`, `Statistics`, `Calibration curve`, `Sources management`.
- `shared-infrastructure`: `Secrets only from .env`, `Optional local LLM behind a profile`, `Network isolation`.

## Impact

- Specs only (`openspec/specs/` through archive). Touches no contract, REST route or event.
