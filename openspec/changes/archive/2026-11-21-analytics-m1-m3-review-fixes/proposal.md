## Why

Kacper's review of PR #35 (`analytics-m1-m3`, review of 6da4f1f) found six required defects and five smaller ones, each reproduced against the code. The worst: the finding text states "not in the KNF register" as fact while the registry is three fictional firms; the bare word `partner` pushes a neutral mention over the M1 alert threshold (0.378 → 0.818); an Instagram post without an author names `instagram.com` as the advertiser; the challenge's own M3 terms ("investment consulting", "doradztwo finansowe", "zarządzanie majątkiem") and English pricing are missing, so an English advisory offer produces no finding; and foreign branches, which are registered in Poland, are dropped as "not targeting Poland". Fixing them before merge keeps M1/M3 output honest for the jury and the demo.

## What Changes

- **Registry wording (item 2, item 9):** the registry loader reports whether it holds the bundled demonstration data (no firm has a `source_url`). S3.1 and the M3 summary say "nie znaleziono w załadowanym rejestrze firm" and, with demonstration data, append "(dane demonstracyjne)"; the M3 title no longer says "spoza rejestru". S3.1 drops its unsourced `art. 69` basis; S3.3/S3.4 cite art. 76 and S3.8 art. 2 u.o.i.f., sourced to the Topic 3 annex, and the crypto statement reads "kryptoaktywa nie są wymienione w katalogu z art. 2 u.o.i.f. (załącznik do tematu 3)".
- **S1.3 labels (item 3):** the bare `partner` is dropped; `#partner` and `partner reklamowy` count, with `współpraca reklamowa` and the hashtags as before.
- **Advertiser on social hosts (item 4):** a social-platform document without an author gets `advertiser.name` and `website` null; the M1 title falls back to "Nieznany autor".
- **M3 vocabulary (item 5):** S3.2 gains `investment consulting`, `wealth advisory`, `doradztwo finansowe`, `zarządzanie majątkiem`; S3.5 gains English pricing (`per month`, `monthly`, `/month`, `subscription`, amounts in PLN/EUR/USD). Every new pattern is linear and timed in `tests/test_redos.py`.
- **Polish-marker filter (item 6):** applies only to `foreign_no_branch`; a branch of a foreign firm is registered in Poland, so its non-Polish ad still reaches M1.
- **Own material of a foreign firm without a branch (item 12, coordinator):** a `foreign_no_branch` firm's own page or account goes to no module (log `out_of_scope_m2_foreign_no_branch`): M2 is only for firms registered in Poland, including Polish branches, and the firm is authorized, so not M3. Third-party ads of it are still M1.
- **Titles and notes (items 7, 8):** M3 titles say "możliwe …" while the deciding signal is `uncertain`; M1 titles say "wspomina" instead of "reklamuje" when no ad signal (S1.2, S1.3, S1.4) fired. When S3.3 is not detected, the M3 summary says that personalisation (art. 76) is unconfirmed. ADR 0308 records the S3.4 gate as a deliberate "may indicate" choice.
- **Excerpt (item 10):** M1/M3 `content_excerpt` is a window of at most 500 characters around the first evidence in the text, not the first 500 characters of the page.
- **Docs (items 1, 11):** a privacy line in `analytics/README.md` (evidence and `advertiser` copy scraped handles, names and links verbatim into findings and events); an M1/M3 row in `.docs/INDEX.md`; a follow-up row linking #26's fix of the `_BOUNDARY` ReDoS in `preprocessing.py` (this PR merges after #26 and gets the fix through the worker merge).

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `m1-third-party-signals`: S1.3 labels, S1.7 filter scope, M1 finding assembly (title verb, excerpt).
- `m3-unauthorized-advice-signals`: S3.1 wording and registry flag, S3.2 and S3.5 vocabulary, S3.8 wording, M3 finding assembly (title, notes, excerpt).
- `document-analysis`: routing (`foreign_no_branch` filter, own material of `foreign_no_branch` firms out of scope), advertiser on social hosts without an author.

## Impact

- Owner: Damian (`analytics/`). Touches no contract, REST route or event; output still validates against `finding.schema.json` v1. Stage 2, on top of `analytics-m1-m3` (PR #35, stacked on #26).
- Code: `registry.py` (`Registry.demo`), `modules/advertiser.py`, `modules/m1.py`, `modules/m3.py`, `modules/excerpt.py` (new), `rules/m1.py`, `rules/m3.py`, `rules/m1_signals.yaml`, `rules/m3_signals.yaml`, `pipeline.py`, `registry/seed.csv` (one fictional `foreign_no_branch` firm for the filter tests), tests.
- Docs: ADR 0308 (number reserved for this change), `.docs/decisions/README.md`, `analytics/README.md`, `analytics/registry/README.md`, `.docs/INDEX.md`, the AI log row.
- Out of scope: the `_BOUNDARY` ReDoS (fixed on #26), `.docs/security-audit.md` (comes with #26), the ~30-firm registry and the real KNF loader (stage 3).
