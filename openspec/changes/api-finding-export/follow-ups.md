# Follow-ups

| Item | Disposition |
|---|---|
| The mock server has no `/findings/{id}/export` (it holds no raw objects), so the "Eksportuj" button 404s in the dashboard's mock mode. | Kept: mocks stay a test double (api/CLAUDE.md); add a mock route only if Kacper needs it for mock-mode demos. |
| `web/src/api/openapi.json` (Kacper's snapshot) does not have the new path. | Kacper re-syncs it with the button PR. |
| PDF output. | Not needed: the HTML page prints to PDF from the browser (`@media print` hides the raw HTML block). |
| `MinioStore._get` (`api/src/investwatch_api/objectstore.py`) calls `response.read()` outside its `except` blocks, so a connection reset mid-body is a 500 instead of `ObjectStoreError`: the export then fails instead of showing `store_down` (the screenshot route too). Pre-existing; found by the `iw-reviewer` pass. | Damian (api), small fix after hand-in. |
