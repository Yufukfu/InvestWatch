# 0105. One `content_hash` normalisation: NFC

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by: pending approval of the `content-hash-definition` PR

## Context

`ScrapedDocument.content_hash` is "sha256 of normalized text" ([integration-plan.md](../integration-plan.md) §3), but the text was never defined once (issue #31, follow-up 6 of `analytics-skeleton`). Two normalisers exist:

- scraper, `normalise_text` in `scraper/src/iw_scraper/ingest/document.py`: Unicode **NFC**, every whitespace run collapsed to one space, trimmed, case kept;
- analytics, `normalize` in `analytics/src/investwatch_analytics/preprocessing.py`: Unicode **NFKC**, `\s+` collapsed to one space, trimmed.

Who uses the value (read in the code on `origin/main`):

- The scraper computes it and stores it. `documents` has `UNIQUE (source_id, content_hash) NULLS NOT DISTINCT WHERE content_hash IS NOT NULL` (`api/migrations/versions/0001_initial.py`), and the scraper inserts with `ON CONFLICT (source_id, content_hash) ... DO NOTHING` plus a pre-check `is_duplicate` ([ADR 0104](0104-ingest-order-and-republish-sweep.md), [ADR 0307](0307-database-driver-and-table-layout.md)). A hit drops the new document silently.
- The API only copies the column (`api/src/investwatch_api/db/mapping.py`); the schema checks `^[a-f0-9]{64}$` and nothing else.
- Analytics loads the stored value into `ScrapedDocument.content_hash` (`storage.py`, `models.py`) and also recomputes one in `preprocess()`. Nothing in `analytics/src` reads either of them yet (`grep content_hash` finds only the definitions, the loader column list and `Preprocessed.content_hash`). The plan keys an LLM response cache by it ([analytics-plan.md](../analytics-plan.md), "Response cache keyed by `(content_hash, prompt_version, model)`"), which is not built.
- Nothing calls the scraper's `Ingestor` yet ([status](../status/scraper.md)), so no production row exists, but the unique index and the spec `document-ingest` already depend on the NFC definition.

The two functions differ only in the compatibility step. Measured with `unicodedata` (Python 3.9): NFKC turns `ﬁ` into `fi`, `m²` into `m2`, `１２` (full-width) into `12`, `…` into `...`, `™` into `TM`, `½` into `1⁄2`, while NFC leaves all of them unchanged; `normalize("NFKC", "10²") == normalize("NFKC", "102")` is `True`. Whitespace handling is equivalent (`str.split()` and `re \s` use the same set for `str`).

## Options considered

1. **NFC everywhere (the scraper's definition).** Stored hashes, the unique index and the existing scraper tests and spec stay as they are. Distinct texts stay distinct: `10²` and `102` are different documents. Analytics must read the stored value or switch its hash function.
2. **NFKC everywhere.** Folds typographic variants (a page that swaps `ﬁ` for `fi` still dedups). But the scraper's hash changes, so any stored hash would no longer match a re-collected page (a one-time duplicate wave), and it merges texts that differ in meaning (`10²` vs `102`, `½` vs `1⁄2`) into one row: `ON CONFLICT DO NOTHING` then discards a real, different document. That is an irreversible loss in a system that looks for risky claims, where figures are the evidence.
3. **Keep both, document the difference.** Two hashes for one text; any cache or join keyed by `content_hash` across services misses silently. The issue exists to avoid exactly this.

## Decision

Option 1. `content_hash` is the lowercase hex sha256 of the UTF-8 bytes of the normalised text, where normalisation is: Unicode NFC, then every run of whitespace (`str.split()` semantics, so the no-break and ideographic spaces count) collapsed to one U+0020, leading and trailing whitespace removed, case kept. Compatibility characters are not folded. The definition is written in [integration-plan.md](../integration-plan.md) §3; the reference implementation is the scraper's `content_hash`, pinned by literal-hash tests in `scraper/tests/test_ingest_document.py`.

The scraper is not changed: it already computes this. Analytics owns its side (Damian): read the stored `content_hash` instead of recomputing it (it is non-null for every row the scraper writes), or if it must hash itself, hash `unicodedata.normalize("NFC", text)` with the same collapse. NFKC stays valid for analytics' own matching (rules, language guess, excerpts), which is a separate, internal text and never stored.

## Consequences

- The dedup key and the future cache key are one value; the scraper's definition cannot drift unnoticed, because its tests use literals.
- Until analytics changes, `Preprocessed.content_hash` still differs from the stored value for text with compatibility characters; it is unused today, so nothing breaks, but a cache built on it before the change would miss. The proposed change is in the reply to issue #31.
- The scraper's pre-upload dedup does not catch a page that only swaps compatibility characters (`ﬁ` for `fi`); it is stored as a new row. Accepted: near-duplicates are analytics' SimHash/MinHash job ([analytics-plan.md](../analytics-plan.md) §2).
- Changing the definition later means a new ADR and re-hashing `documents` in a migration.
