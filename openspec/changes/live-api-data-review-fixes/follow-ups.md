# Follow-ups

- For Damian: `openspec/changes/api-v1` (`proposal.md` around line 41, `design.md` around line 43) still names web "mock mode" as the rollback. Web has no mock mode now; the fallback is running `contracts/mock-server` as a separate container.
- `scripts/sync-contracts.mjs`: the write path (without `--check`) and orphan removal are untested.
