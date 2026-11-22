# Proposal

## Why

The CI job `Specs and hooks` runs `npx -y @fission-ai/openspec@2.1.1 validate --all --strict`. In strict mode a warning fails the run, and OpenSpec 2.1.1 warns when a requirement's text before its first scenario is longer than 500 characters. Three requirements merged after `openspec-strict-format` (#37) are over the limit, so the job is red for everyone on `main`:

- `rest-api`, `Finding detail with its document`: 1340 characters, with the rescan state from #87.
- `rest-api`, `Evidence pack of a finding`: 1055 characters, from #104.
- `shared-infrastructure`, `Optional local LLM behind a profile`: 505 characters, from #86 (`infra-ollama-bge-m3`).

The local OpenSpec 1.2.0 has no such check, which is how they got through.

## What Changes

This is a format-only change, made the way #37 did it:

- **Kept:** each requirement keeps its header, its main SHALL statements and every scenario it already has.
- **Moved:** the sentences that pushed a requirement over 500 characters move, word for word where possible, into `**AND**` lines on the scenario of the same requirement that already tests that rule.
- **One new scenario:** `Page returns to earlier text` (rest-api), because no existing scenario covered that sentence.
- **Not touched:** no requirement is renamed, split, added or removed, and no scenario is renamed or removed.

Result: 416, 463 and 436 characters.

## Out of scope

- **Behaviour:** no behaviour, contract, REST route, event or code changes.
- **Owners:** `rest-api` belongs to Damian (`api/`). `shared-infrastructure` is Kacper's (`infra/`), so he reviews the format-only edit to his spec.
