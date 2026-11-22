# Tasks

## 1. Isolate untrusted text in screen-reader strings and the server detail

- [x] 1.1 Write failing tests: `isolate()` wraps in FSI/PDI, drops a stray PDI, closes an open isolate, turns a paragraph separator into a space and keeps everything else; the toast group and close button names and the live announcement hold the FSI/PDI-wrapped title for a U+202E title; the StatusEditor server detail with U+202E sits in a `dir="auto"` element holding only that text. Update the tests that query toasts by name. Verify they fail first. Red against an identity `isolate()` stub and the old `StatusEditor`: 21 assertion failures across the six files, no import errors.
- [x] 1.2 Add `web/src/format/bidi.ts` and use it in `AlertToasts.tsx` and `useRealtime.ts`; add `dir="auto"` in `StatusEditor.tsx`. Verify tests, lint, typecheck.
- [x] 1.3 Mutation check; list every mutant and result on this line. Mutants, scripted (snippet asserted, file restored and hash-checked), each run against its own test file: leading FSI dropped; final PDI dropped; stray PDI kept; open isolates not closed; FSI not counted as an opener; paragraph separators kept; U+0085 missing from the separators; toast group `aria-label` not isolated; close button `aria-label` not isolated; announcement not isolated; stored alert title isolated (visible title no longer verbatim); `dir` dropped from the server detail span; the `Odpowiedź serwera:` label moved into that span. The script first scored the last one as a survivor because it looked only for `AssertionError`; its red was the test's own `getByText(detail)` failing at `StatusEditor.test.tsx:70`, a valid red. mutations: 13 tried, 13 caught.

## 2. Closing

- [x] 2.1 Apply `iw-docs-update` (docs, `.docs/status/dashboard.md`, ADRs) and add the `iw-ai-log` entry. Rule added to `.claude/rules/web-dashboard.md`; no ADR (no hard-to-reverse choice, no new dependency).
- [ ] 2.2 Run `iw-pr-review` and fix real findings.
