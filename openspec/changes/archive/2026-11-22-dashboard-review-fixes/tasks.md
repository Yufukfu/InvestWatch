# Tasks

## 1. Review fixes

- [x] 1.1 Write the failing tests first: `?finding=<id>` and a filter-only link with no hash open the findings page (hash rewritten without a history entry), an explicit hash wins; the `3` shortcut with an unsaved note sends no PATCH and keeps the note
- [x] 1.2 Implement `hasFindingsParams` and the fallback in `App`, `onDirtyChange` in `StatusEditor` and the guard in the shortcuts
- [x] 1.3 Run typecheck, lint, the suite and the build
- [x] 1.4 mutations: 8 tried, 8 caught

## 2. Closing

- [x] 2.1 Apply `iw-docs-update` and add the AI-log entry
- [x] 2.2 Run the `iw-pr-review` skill and fix real findings (iw-reviewer on `01efdcdd..9aae3065`, merge resolution and fixes: no blocking findings)
