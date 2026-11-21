# Follow-ups

| Finding (iw-reviewer, whole branch) | Disposition |
|---|---|
| Summary hook has no error flag, spec scenario overstated it | fix-here: scenario reworded, behaviour unchanged |
| Summary failure test used a bare sleep | fix-here: waits for the handler to be hit |
| `**/data` pattern too broad, pages and other features' data not covered | fix-here: anchored patterns plus `**/*Page`, tests added (5 patterns mutated, all caught) |
| No accept case for `../model`, no reject case for type-only imports from `api/` | fix-here: cases added |
| `layering.test.ts` spawned `.bin/oxlint` (breaks on Windows) | fix-here: runs oxlint's JS entry with `process.execPath`, `-f unix` |
| `SummaryCounts`/`HealthState` live in components, not `model.ts` | wont-fix: ADR 0204 requires `model.ts` only for non-trivial DTOs; flat types stay with the component |
| `App.test.tsx` builds its own store instead of `test/store.tsx` | wont-fix: the spec keeps `App.test.tsx` unchanged as the integration test |
