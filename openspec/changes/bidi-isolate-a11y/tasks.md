# Tasks

## 1. Bidi isolation in screen-reader text and the server detail

- [x] 1.1 Write failing tests: `isolate` wraps a value in U+2068/U+2069; a toast whose title contains U+202E has the accessible name `Wysokie ryzyko: <U+2068>title<U+2069>` and a `Zamknij: <U+2068>title<U+2069>` button; `useRealtime` announces `Wysokie ryzyko: <U+2068>title<U+2069>`; a rejected save whose `detail` contains U+202E shows it in a `dir="auto"` `lang="en"` element holding only the detail. Verify they fail first.
- [x] 1.2 Add `web/src/format/bidi.ts` and use it in `AlertToasts.tsx` and `useRealtime.ts`; add `dir="auto"` to the detail span in `StatusEditor.tsx`; build the accessible names in the existing toast tests with `isolate`. Verify tests, lint, typecheck, build.
- [x] 1.3 Mutation check; list every mutant and result on this line. Mutants, each run against its own test file: `isolate` returns the text unchanged; drops the PDI; uses LRI (U+2066) instead of FSI; toast `aria-label` without `isolate`; `Zamknij` `aria-label` without `isolate`; live-region announcement without `isolate`; `dir` dropped from the detail span; `lang` dropped from it; `Odpowiedź serwera:` moved inside it. mutations: 9 tried, 9 caught.

## 2. Closing

- [ ] 2.1 Apply `iw-docs-update` (docs, `.docs/status/dashboard.md`, ADRs) and add the `iw-ai-log` entry.
- [ ] 2.2 Run `iw-pr-review` and fix real findings.
