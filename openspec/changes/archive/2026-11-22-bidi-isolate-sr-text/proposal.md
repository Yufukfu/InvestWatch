# Proposal

## Why

Change `untrusted-text-plain` (PR #91, issue #54) put every untrusted finding value alone in a `dir="auto"` element. Two places it left out are tracked in issue #99 (from the review of PR #91):

1. Screen-reader strings join the alert title with UI text in one flat string: the toast group's `aria-label` (`Wysokie ryzyko: <title>`), the close button's `aria-label` (`Zamknij: <title>`) and the polite live announcement set in `useRealtime.ts` (`Wysokie ryzyko: <title>`). A `dir` attribute cannot apply inside an attribute value, and an accessible name built with `aria-labelledby` is flattened to plain text as well (the accname algorithm has no bidi handling), so a U+202E in the title can still reorder that string wherever it is drawn as text (the VoiceOver caption panel, a braille display, an accessibility tree viewer).
2. `StatusEditor.tsx` shows the server's `error` text after the Polish label `Odpowiedź serwera:` in a `<span lang="en">` with no `dir`.

## What Changes

- A new helper `isolate()` in `web/src/format/bidi.ts` wraps a value in U+2068 FIRST STRONG ISOLATE and U+2069 POP DIRECTIONAL ISOLATE, the plain-text counterpart of `dir="auto"` (UAX #9). The value is balanced first, so it cannot break out of the wrapper: a PDI with no opener in the value is dropped, an isolate the value leaves open is closed before the final PDI, and a paragraph separator (bidi class B, which ends every isolate) becomes a space. Embeddings and overrides (U+202A–U+202E) need no closing: the final PDI ends them (UAX #9 rule X6a). Nothing else in the value changes.
- The toast group's `aria-label`, the close button's `aria-label` and the live announcement use `isolate(title)`.
- The server detail span in `StatusEditor.tsx` gets `dir="auto"`.

Why FSI/PDI and not `aria-labelledby`: an accessible name or a live announcement reaches assistive technology as one flat string, whatever DOM it came from. `aria-labelledby` pointing at the `dir="auto"` title would lose the isolation when the name is flattened; FSI/PDI are characters in the string itself, so they survive flattening and apply wherever the string is drawn. One helper serves the attributes and the live text, and the visible title stays exactly as it is.

Out of scope: rewriting or stripping bidi controls in the visible title (it stays verbatim in its `dir="auto"` element); other `aria-label`s, which hold no untrusted text; the Polish `error.message`, which comes from a fixed table in `useStatusChange.ts`.

Module: `web/` (Kacper). No contract, REST route or event changes.

## Capabilities

### New Capabilities

### Modified Capabilities

- `web-alerts`: adds a requirement on the title inside screen-reader strings.
- `web-findings`: adds a requirement on the server's error detail.

## Impact

- Code: `web/src/format/bidi.ts` (new), `web/src/features/alerts/components/AlertToasts.tsx`, `web/src/features/alerts/data/useRealtime.ts`, `web/src/features/findings/components/StatusEditor.tsx`, and their tests. Tests that query toasts by accessible name now include the isolate marks.
- Visible behaviour: none. Screen readers read the same words.
