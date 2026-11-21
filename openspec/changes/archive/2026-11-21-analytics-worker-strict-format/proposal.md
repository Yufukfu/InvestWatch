# Proposal

## Why

CI's `Specs and hooks` job runs OpenSpec 2.1.1 `validate --all --strict`, which fails a requirement whose text before the first scenario is longer than 500 characters. `main` fixed its own specs in `openspec-strict-format` (PR #37). Six requirements that exist only on this branch (from `analytics-worker` and its review fixes) are over the limit: five in `document-stream-worker` and one in `finding-storage`. The local OpenSpec 1.2.0 has no such check, so they went unnoticed.

## What Changes

- Each of the six requirements keeps its header, its SHALL statements and every scenario. The sentences over the limit move into the same requirement's scenarios, word for word where possible: as an `**AND**` line on the scenario that already tests that rule, or as a new scenario where none did (2 new: `Health with both dependencies up` and `Upsert key and replaced fields`).
- No requirement is renamed, split, added or removed; no scenario is renamed or removed. No behaviour, code, contract, REST route or event changes.
- Owner: Damian (`analytics/`). Same method as `openspec-strict-format`.

## Capabilities

### Modified Capabilities
- `document-stream-worker`: `Duplicate delivery is idempotent`, `Poison messages`, `Infrastructure outages`, `Observability and graceful stop`, `Container`.
- `finding-storage`: `One finding per document and module`.

## Impact

- Specs only (`openspec/specs/` through archive).
