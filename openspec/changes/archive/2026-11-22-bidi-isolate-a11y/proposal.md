# Proposal

## Why

`untrusted-text-plain` (PR #91) gave every untrusted field on screen its own `dir="auto"` element. @hen68's review found two places it left out (issue #99):

1. Screen-reader text interpolates the alert title into a string with no bidi isolation: the toast `aria-label`s (`Wysokie ryzyko: <title>`, `Zamknij: <title>`) and the polite live-region announcement set by `useRealtime`. A `dir` attribute cannot apply inside an attribute string, so a bidi control in the title (for example U+202E) is not contained.
2. `StatusEditor` shows the server's `error.detail` after the Polish label `Odpowiedź serwera:` in a `<span lang="en">` with no `dir`.

## What Changes

- A shared helper `isolate(text)` in `web/src/format/bidi.ts` wraps a value in U+2068 FIRST STRONG ISOLATE and U+2069 POP DIRECTIONAL ISOLATE, the plain-text equivalent of `dir="auto"`. The two toast `aria-label`s and the live-region announcement use it for the title.
- The `error.detail` span in `StatusEditor` gets `dir="auto"` and keeps `lang="en"`.

Out of scope: stripping or rewriting bidi controls inside the title (shown verbatim, as before); `firm.name` and `rule.name` (not scraped or model text, `wont-fix` in `untrusted-text-plain`'s follow-ups).

Module: `web/` (Kacper). No contract, REST route or event changes.

## Capabilities

### New Capabilities

### Modified Capabilities

- `web-alerts`: adds a requirement that the title is bidi-isolated in screen-reader text.
- `web-findings`: adds a requirement that the server's error detail has its own direction.

## Impact

- Code: `web/src/format/bidi.ts` (new), `web/src/features/alerts/components/AlertToasts.tsx`, `web/src/features/alerts/data/useRealtime.ts`, `web/src/features/findings/components/StatusEditor.tsx`, and their tests. Tests that look a toast up by its accessible name now build the name with `isolate`.
