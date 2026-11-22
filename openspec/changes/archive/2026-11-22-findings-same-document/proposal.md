# Proposal

## Why

Since `analytics-m1-m3` (#35), one post can produce several findings: M1 (firm and advertiser) and M3 (the unregistered author), unique per `(document_id, module)`. The dashboard lists them as unrelated rows. Nothing says they describe the same material, and the analyst reads the same excerpt and screenshot twice. Issue #33 asks the dashboard to handle this. The challenge asks for module results combined into one object (Opis Wyzwania p.2: "agregator łączący wyniki 1,2,3 w ujednolicone obiekty").

## What Changes

- **The detail becomes a view of the material.** Opening any finding loads every finding of its document (`GET /findings?document_id=…`). The detail shows a module switcher (`M1 · M3`) above the module-specific part: rules, score, risk and the analyst's decision. The shared part (source, excerpt, screenshot, parties) is shown once. Switching sets `finding=<id>` in the URL, so a deep link and the back button work as before.
- **The list stays one row per finding.** Each finding keeps its own status and decision, and the module filter keeps working. Each row shows the source host under the title as text, so rows of one post are recognisable.
- Tests build an M1+M3 pair inline. The Vitest fixtures are synced from `contracts/mocks`, so they get the pair only with Damian's mock change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-findings`: new requirements "Detail shows every module of the material" and "Rows show the source host". The existing "Finding detail" requirement is unchanged: one finding is still loaded from `GET /findings/{id}`.

## Impact

- Module: `web/` (Kacper), in `web/src/features/findings/`.
- **Depends on Damian (asked in #33):** an optional `document_id` query parameter on `GET /findings` in `contracts/openapi.yaml` and in `api/`. The web client is generated from that file, and `web/` never hand-writes a request, so the switcher (task group 2) starts only after that contract change is merged and the snapshot is regenerated. Task group 1 (host and model) needs nothing from outside.
- For the demo on the mock server, `contracts/mocks/findings.json` needs one document with M1 and M3 (also asked in #33).
- Out of scope: merging findings into one row, a list grouped per document, and a shared status for all modules of a document.
