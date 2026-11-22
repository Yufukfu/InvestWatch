## 1. Gone job errors from the scraper

- [x] 1.1 Failing tests in `api/tests/test_findings.py`: a `gone` row marks removed (and `http_error` still does), a `gone` row with the entered URL on a redirecting web source marks removed; both fail on `main`
- [x] 1.2 `api/src/investwatch_api/rescan.py`: `reason IN ('gone', 'http_error')`; web documents with a `source_id` match by `source_id`, other platforms keep the URL match
- [x] 1.3 Guard tests: another reason with a 404 detail, another web source, another page of a many-page source are ignored
- [x] 1.4 Mutation check (`reason` filter both ways, the web/source branch forced on, off, without its platform or `source_id` guard, the source match inverted). mutations: 7 tried, 7 caught

## 2. Closing

- [x] 2.1 Docs: `api/README.md`, `.docs/status/platform.md`
- [x] 2.2 AI log entry (`iw-ai-log`)
- [x] 2.3 Review (`iw-reviewer`, range a0ad3d13..cb8060ef, security folded in): no blocking findings
