## 1. Catalogue and CLI robustness

- [x] 1.1 Test: bad `negation_before` / `prominent_sentences` / `footnote_markers` and a list root raise `CatalogueError`; one document whose analysis raises is skipped, the rest are written, exit 1; registry error names `REGISTRY_CSV`
- [x] 1.2 `_check_params` and root check in `Catalogue.load`; per-document guard in `cli.main`; registry error hint
- [x] 1.3 Mutation check — mutations: 13 tried, 13 caught

## 2. Matching and rule text

- [x] 2.1 Test: `Alfa-Beta Inwestycji` fuzzy-matches `Alfa-Beta Inwestycje`; `bez opłat ryzyko utraty` is a warning; `to nie tylko reklama` passes R2
- [x] 2.2 `_best_fuzzy` tokenization, R3 exclusion patterns, R2 `negation_before`
- [x] 2.3 Mutation check — mutations: 7 tried, 7 caught (first run 6/7: the hyphen mutant survived on a long name; a short-name test was added)

## 3. Reviewer fixes

- [x] 3.1 Test: plural and `nie ma` / `nie istnieje` denials fail R3; empty label and unknown param key fail at load; a punctuation-only name never fuzzy-matches
- [x] 3.2 R3 denial pattern (`ryzyka?`, `żadn…`, `nie ma`, `nie istnieje`), `KNOWN_PARAMS` and non-empty labels, `_best_fuzzy` empty guard
- [x] 3.3 Mutation check — mutations: 8 tried, 8 caught

## 4. Closing

- [x] 4.1 Apply iw-docs-update and add the iw-ai-log row
- [x] 4.2 Run iw-pr-review checks and a fresh review; fix real findings (iw-reviewer: 1 high, 3 low, all verified and fixed in group 3; declined items in `follow-ups.md`)
