## 1. Contract and mocks (after the team's OK; commits use `IW_CONTRACT_CHANGE=1`)

- [x] 1.1 Failing check first: a mock-server store test that expects one `document_id` shared by an M1 and an M3 finding, and counts 11 findings / 10 documents
- [x] 1.2 `contracts/openapi.yaml`: optional `document_id` (string, uuid) on `GET /findings`; `info.version` 1.0.0 → 1.1.0
- [x] 1.3 `generate_mocks.py`: scenarios may carry `findings=[...]`; add the M1 + M3 Instagram post; regenerate the mocks; `python contracts/validate.py` exits 0
- [x] 1.4 Update the mock-server tests that pin mock counts
- [x] 1.5 Mutation check (iw-commit-cycle step 3). mutations: 3 tried, 3 caught

## 2. Mock server filter

- [x] 2.1 Failing tests first: `document_id` alone, with `module=`, with pagination, unknown UUID (200, empty) and malformed value (422)
- [x] 2.2 `iw_mock_server/app.py`: `document_id: UUID | None` on `GET /api/findings`; FastAPI version 1.1.0
- [x] 2.3 Mutation check. mutations: 3 tried, 3 caught

## 3. API filter

- [x] 3.1 Failing tests first (real Postgres): two findings on one document plus another document; `document_id` alone, with `module=`, with `sort` + pagination, unknown UUID, malformed value (422 naming `document_id`); the response validates against `contracts/openapi.yaml`
- [x] 3.2 `routes/findings.py`: `document_id: UUID | None` adds `findings.c.document_id == document_id`; `app.py` version 1.1.0
- [x] 3.3 Mutation check. mutations: 3 tried, 3 caught

## 4. Closing tasks

- [x] 4.1 Apply the iw-docs-update skill (`.docs/integration-plan.md` §5 filter list, `contracts/README.md` version note, `api/README.md` if it lists filters, `.docs/status/platform.md`; docs-check clean) and add the iw-ai-log row
- [x] 4.2 Run the iw-pr-review skill (one iw-reviewer pass including security, because a contract changes) and fix real findings
