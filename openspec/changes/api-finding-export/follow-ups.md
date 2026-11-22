# Follow-ups

| Item | Disposition |
|---|---|
| The mock server has no `/findings/{id}/export` (it holds no raw objects), so the "Eksportuj" button 404s in the dashboard's mock mode. | Kept: mocks stay a test double (api/CLAUDE.md); add a mock route only if Kacper needs it for mock-mode demos. |
| `web/src/api/openapi.json` (Kacper's snapshot) does not have the new path. | Kacper re-syncs it with the button PR. |
| PDF output. | Not needed: the HTML page prints to PDF from the browser (`@media print` hides the raw HTML block). |
