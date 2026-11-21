## 1. Catalogue and CLI robustness

- [x] 1.1 Test: bad `negation_before` / `prominent_sentences` / `footnote_markers` and a list root raise `CatalogueError`; one document whose analysis raises is skipped, the rest are written, exit 1; registry error names `REGISTRY_CSV`
- [x] 1.2 `_check_params` and root check in `Catalogue.load`; per-document guard in `cli.main`; registry error hint
- [x] 1.3 Mutation check — mutations: 13 tried, 13 caught

## 2. Matching and rule text

- [x] 2.1 Test: `Alfa-Beta Inwestycji` fuzzy-matches `Alfa-Beta Inwestycje`; `bez opłat ryzyko utraty` is a warning; `to nie tylko reklama` passes R2
- [x] 2.2 `_best_fuzzy` tokenization, R3 exclusion patterns, R2 `negation_before`
- [x] 2.3 Mutation check — mutations: 7 tried, 7 caught (first run 6/7: the hyphen mutant survived on a long name; a short-name test was added)

## 3. Closing

- [x] 3.1 Apply iw-docs-update and add the iw-ai-log row
- [ ] 3.2 Run iw-pr-review checks and a fresh review; fix real findings
