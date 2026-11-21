# Follow-ups

| # | Source | Finding | Disposition |
|---|---|---|---|
| 1 | review | `.docs/analytics-plan.md` §2 row 1 says "normalize (Unicode NFKC, ...), dedup by `content_hash`", which reads as an NFKC hash; the file is Damian's | `new-item`: Damian adds "(NFKC for matching only; `content_hash` is NFC, ADR 0105)" together with the analytics change proposed in issue #31 |
| 2 | review | `analytics/` `content_hash` still NFKC (`preprocessing.py`) | `new-item`: issue #31, Damian; the analytics change also MODIFIES `openspec/specs/document-analysis/spec.md` requirement "Preprocessing" (says NFKC and "sha256 of the normalized text") |
| 3 | review | `assert content_hash(text) != content_hash(folded)` is redundant with the literal assertion | `wont-fix`: it states the intent (not folded) next to the literal; harmless |
| 4 | review | `contracts/mocks/generate_mocks.py` `sha()` lowercases and applies no NFC, so none of the 9 `content_hash` values in `contracts/mocks/documents.json` (copied into `web/src/test/fixtures/documents.json` and `finding-detail.json`) match the definition | `new-item`: Damian decides whether to regenerate (contracts are frozen; nothing dedups on them), Kacper's fixture copies follow |
| 5 | review | spec scenario "Canonically equivalent text" had lost its decomposed literal; ADR whitespace set was Python-only; ADR cited Python 3.9 | `fixed`: this PR (escapes in the scenario, exact set and 3.12/3.13 measurements in the ADR and plan) |
