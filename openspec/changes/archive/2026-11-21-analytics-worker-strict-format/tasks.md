# Tasks

## 1. Fit the six requirements to OpenSpec 2.1.1

- [x] 1.1 MODIFIED deltas for the six requirements, overflow text moved into scenarios; `npx -y @fission-ai/openspec@2.1.1 validate --all --strict` passes
- [x] 1.2 Mutation check; `mutations: n/a, specs only (no code)`

## 2. Closing

- [x] 2.1 Apply the iw-docs-update skill (`docs-check` clean; no doc outside `openspec/` changes) and add the iw-ai-log row (covered by the `analytics-worker-review-fixes` row: same PR)
- [x] 2.2 Run the iw-pr-review skill (specs-only change: `openspec validate --all --strict` with 2.1.1, docs-check)
