## Why

Issue #31: `content_hash` is "sha256 of the normalised text" (`.docs/integration-plan.md` §3), but the scraper normalises with NFC and analytics with NFKC, so text with compatibility characters (ligature `ﬁ`, superscript `²`, full-width digits) can get two hashes. The definition was never written down once.

## What Changes

- One definition goes into `.docs/integration-plan.md` §3 and [ADR 0105](../../../.docs/decisions/0105-content-hash-normalisation.md): NFC, whitespace runs collapsed to one space, trimmed, case kept, UTF-8, sha256 hex. The scraper already does exactly this, so stored hashes (and the unique dedup index on `documents`) do not change.
- A scraper test pins the definition with literal hashes, including compatibility characters.
- The `document-ingest` requirement states that compatibility characters are not folded.
- Analytics keeps its NFKC `normalize` for rule matching, language guess and excerpts; the proposed change to its `content_hash` is in the issue reply, not made here.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `document-ingest`: the content hash keeps compatibility characters as they are (NFC, not NFKC).

## Impact

- Owner: Adam (`scraper/`, docs). No code change in `scraper/src`. Touches no contract file, REST route or event; `content_hash` keeps its schema (`^[a-f0-9]{64}$`), only its prose definition is written down.
- Out of scope: `analytics/` (Damian's service), `contracts/`.
