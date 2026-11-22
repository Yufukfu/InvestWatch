# Proposal

## Why

Review of PR #137 found two blocking defects: (1) the `1`-`5` status shortcut saves only the status and then the editor resets, silently discarding an unsaved note; (2) a link with a finding or findings filters but no hash (a pre-split bookmark, a hand-typed demo link) now shows the overview, breaking the web-findings "Deep link" requirement.

## What Changes

- **Shortcut vs unsaved edits**: while the status editor has unsaved changes (a changed status choice or note), the `1`-`5` shortcuts do nothing, so a draft is never overwritten.
- **Deep links without a hash**: when the hash is empty or unknown and the query string carries a findings parameter (`finding`, `triage`, or any filter, sort or paging parameter), the findings page shows and the hash is rewritten to `#zgloszenia` in place (no history entry).
- Touches no contract, route or event. Owner: `web/`.

## Capabilities

### Modified Capabilities
- `web-navigation`: deep links without a hash resolve to the findings page.
- `web-triage`: the status shortcuts never discard unsaved edits.

## Impact

- `web/src/App.tsx`, `web/src/url/section.ts`, `web/src/features/findings/` (`StatusEditor`, `FindingsPage`, `useFindingShortcuts`) and their tests.
