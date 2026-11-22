# Tasks

## 1. Isolate untrusted text in screen-reader strings and the server detail

- [ ] 1.1 Write failing tests: `isolate()` wraps in FSI/PDI, drops a stray PDI, closes an open isolate, turns a paragraph separator into a space and keeps everything else; the toast group and close button names and the live announcement hold the FSI/PDI-wrapped title for a U+202E title; the StatusEditor server detail with U+202E sits in a `dir="auto"` element holding only that text. Update the tests that query toasts by name. Verify they fail first.
- [ ] 1.2 Add `web/src/format/bidi.ts` and use it in `AlertToasts.tsx` and `useRealtime.ts`; add `dir="auto"` in `StatusEditor.tsx`. Verify tests, lint, typecheck.
- [ ] 1.3 Mutation check; list every mutant and result on this line.

## 2. Closing

- [ ] 2.1 Apply `iw-docs-update` (docs, `.docs/status/dashboard.md`, ADRs) and add the `iw-ai-log` entry.
- [ ] 2.2 Run `iw-pr-review` and fix real findings.
