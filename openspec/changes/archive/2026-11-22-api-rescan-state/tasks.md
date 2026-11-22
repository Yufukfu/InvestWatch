## 1. Re-scan state on the finding detail

- [x] 1.1 `api/src/investwatch_api/rescan.py`: derive `{state, latest_document_id, checked_at}` from later `documents` of the same page and gone `job_errors`
- [x] 1.2 `GET /api/findings/{id}` serves it as `document.scrape_meta.rescan`, keeping the scraper's keys
- [x] 1.3 Tests in `api/tests/test_findings.py`: current, changed, removed (404/410 document, later job error), canonical URL, unrelated rows ignored, schema-valid detail

## 2. Closing

- [x] 2.1 Docs: `api/README.md`, `.docs/status/platform.md`, `follow-ups.md` (list badge needs a contract field)
- [x] 2.2 AI log row in `.docs/ai-workflow.md`
- [x] 2.3 PR review (`iw-pr-review`)
