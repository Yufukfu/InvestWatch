# Tasks

## 1. Shorten the three requirements (~15 min)

- [x] 1.1 `npx -y @fission-ai/openspec@2.1.1 validate --all --strict` on `main` 5cb9138: `rest-api` and `shared-infrastructure` fail with three "Requirement text is very long" warnings (the failing check, before the change)
- [x] 1.2 MODIFIED deltas move the extra sentences into the requirements' scenarios (416, 463 and 436 characters)
- [x] 1.3 Mutation check; `mutations: n/a, specs-only format change with no code, guard or test`

## 2. Closing

- [x] 2.1 `validate --all --strict` with 2.1.1 passes, and `docs-check` is clean
- [x] 2.2 AI log entry (`iw-ai-log`)
- [x] 2.3 Archive the change (last commit)
