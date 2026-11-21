# Follow-ups

Out-of-scope reviewer findings and "declined to judge" items, one disposition each.

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | review group 1 | `Finding.advertiser` and `RuleResult.evidence_locator` are not modelled (allowed by the schema; needed by M1/M3 and the visual rules R4-R8) | `new-item`: add with the M1/M3 and visual-rules changes |
| 2 | review group 1 | Input fields `media`, `screenshots`, `http_status`, `html_object_key`, `scrape_meta` are ignored by the lenient input model | `new-item`: model them when OCR / screenshot rules land |
| 3 | review group 1 | The default `REGISTRY_CSV` path resolves via `parents[2]` and only works from source / an editable install | `docs`: the Dockerfile in `analytics-worker` sets `REGISTRY_CSV` explicitly; since `analytics-skeleton-review-2-fixes` (PR #10 second review) the error says to set `REGISTRY_CSV`, and `analytics/README.md` says the default only works from source |
| 4 | review group 1 | An invalid `LOG_LEVEL` raises at startup | `wont-fix`: failing loudly on bad config is intended |
| 5 | review group 1 | `pyproject.toml` declared no runtime dependencies | `fix-here`: added in the review-fix commit |
| 6 | review group 2 | `content_hash` normalization (NFKC, collapse `\s+`, strip, UTF-8 sha256) is not written down for the scraper, so dedup across services may diverge | `new-item`: agree the definition with Adam and record it in `.docs/integration-plan.md` §3 |
| 7 | review group 2 | One language per document; R10 (warning language vs main message) will need per-sentence language | `new-item`: with R10 |
| 8 | review group 2 | Zero-width space and soft hyphen are not stripped by `normalize` | `wont-fix` for now: not in the spec, revisit if dedup misses real duplicates |
| 10 | review group 3 | On a `firm_own` page, a name match for another firm (e.g. a custodian bank) beats the page's own domain, so R1 may judge the wrong firm | `fix-here` in `analytics-skeleton-review-fixes` (PR #10 review): the firm whose domain hosts the page wins; name ties go to the earliest, then longest quote |
| 11 | review group 3 | Fuzzy match still accepts one-letter variants of common words (`bank przykładowo` → Bank Przykładowy, 0.80) | `wont-fix` for now: a fuzzy match never makes R1 pass, and the confidence is on the finding; revisit for M1/M3 |
| 12 | review group 3 | Inflected names (`Banku Przykładowego`) and spaced-out names are not matched | `new-item`: alias stems or lemmatization with the real KNF loader |
| 13 | review group 3 | `FIRM_TYPES` duplicates `models.RegistryType` | `wont-fix`: same values, one-line sync if the contract enum changes |
| 14 | review group 4 | `stop\w* zwrotu` needs exactly one space; `Zyskaj dostęp` counts as a return claim | `wont-fix` for now: regex-version limits, borderline cases go to the LLM layer (plan §5) |
| 15 | review group 4 | R2 dictionary lacks `materiał sponsorowany` / `współpraca reklamowa` | `new-item`: decide with M1 (S1.3) which labels count as an ad label for R2 |
| 16 | review group 5 | Summary says "Sprawdzono reguły R1, R2, R3" even when a rule was `not_applicable` | `fix-here` in `analytics-skeleton-review-fixes` (PR #10 review): only applicable rules are listed as checked, `not_applicable` ones under "Nie dotyczy" |
| 17 | review group 5 | `content_excerpt` comes from the NFKC-normalized text, not the original | `wont-fix`: the contract does not say; normalized text reads better in the dashboard |
| 18 | review group 5 | `FirmRef.authorized=True` is hard-coded for every registry match | `new-item`: revisit with the real KNF loader (warning list, revoked licences) |
| 19 | review group 5, final review | Denial exclusions swallowed real warnings with a double negative | `fix-here` for the common disclaimers (`nie są wolne od ryzyka`, `nie ma inwestycji bez ryzyka`, `no investment is risk-free`, `not risk-free`) via `risk_override_patterns`; negated exclusions of loss (`nie jest wykluczona utrata`, `nie wykluczamy strat`, `nie gwarantujemy braku strat`) `fix-here` in `analytics-skeleton-review-fixes` (PR #10 review); `wont-fix` for now for `bez względu na ryzyko`, left to the LLM layer |
| 9 | review group 2 | Initials like `J. Kowalski` split into two sentences | `wont-fix` for now: rare in marketing copy, only lengthens or shortens a quote |
