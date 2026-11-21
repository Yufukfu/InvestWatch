# Follow-ups

Out-of-scope reviewer findings and "declined to judge" items, one disposition each.

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | review group 1 | `Finding.advertiser` and `RuleResult.evidence_locator` are not modelled (allowed by the schema; needed by M1/M3 and the visual rules R4-R8) | `new-item`: add with the M1/M3 and visual-rules changes |
| 2 | review group 1 | Input fields `media`, `screenshots`, `http_status`, `html_object_key`, `scrape_meta` are ignored by the lenient input model | `new-item`: model them when OCR / screenshot rules land |
| 3 | review group 1 | The default `REGISTRY_CSV` path resolves via `parents[2]` and only works from source / an editable install | `docs`: the Dockerfile in `analytics-worker` sets `REGISTRY_CSV` explicitly |
| 4 | review group 1 | An invalid `LOG_LEVEL` raises at startup | `wont-fix`: failing loudly on bad config is intended |
| 5 | review group 1 | `pyproject.toml` declared no runtime dependencies | `fix-here`: added in the review-fix commit |
| 6 | review group 2 | `content_hash` normalization (NFKC, collapse `\s+`, strip, UTF-8 sha256) is not written down for the scraper, so dedup across services may diverge | `new-item`: agree the definition with Adam and record it in `.docs/integration-plan.md` §3 |
| 7 | review group 2 | One language per document; R10 (warning language vs main message) will need per-sentence language | `new-item`: with R10 |
| 8 | review group 2 | Zero-width space and soft hyphen are not stripped by `normalize` | `wont-fix` for now: not in the spec, revisit if dedup misses real duplicates |
| 10 | review group 3 | On a `firm_own` page, a name match for another firm (e.g. a custodian bank) beats the page's own domain, so R1 may judge the wrong firm | `new-item`: decide with Damian whether `firm_own` prefers the domain match; current behaviour follows design decision 4 |
| 11 | review group 3 | Fuzzy match still accepts one-letter variants of common words (`bank przykładowo` → Bank Przykładowy, 0.80) | `wont-fix` for now: a fuzzy match never makes R1 pass, and the confidence is on the finding; revisit for M1/M3 |
| 12 | review group 3 | Inflected names (`Banku Przykładowego`) and spaced-out names are not matched | `new-item`: alias stems or lemmatization with the real KNF loader |
| 13 | review group 3 | `FIRM_TYPES` duplicates `models.RegistryType` | `wont-fix`: same values, one-line sync if the contract enum changes |
| 14 | review group 4 | `stop\w* zwrotu` needs exactly one space; `Zyskaj dostęp` counts as a return claim | `wont-fix` for now: regex-version limits, borderline cases go to the LLM layer (plan §5) |
| 15 | review group 4 | R2 dictionary lacks `materiał sponsorowany` / `współpraca reklamowa` | `new-item`: decide with M1 (S1.3) which labels count as an ad label for R2 |
| 9 | review group 2 | Initials like `J. Kowalski` split into two sentences | `wont-fix` for now: rare in marketing copy, only lengthens or shortens a quote |
