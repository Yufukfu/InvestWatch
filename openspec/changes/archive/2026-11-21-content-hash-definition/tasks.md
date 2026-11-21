## 1. Pin the definition in the scraper

- [x] 1.1 Test: literal hashes for compatibility characters (ligature, superscript, full-width digits), NFD versus NFC, no-break and ideographic space
- [x] 1.2 Mutation check on `normalise_text` and `content_hash`: mutations: 6 tried, 6 caught (NFC to NFKC, no collapse, split on one space only, lowercase, NFD, UTF-16). The new tests are green on unchanged code because the scraper already follows the definition; the red proof is the mutants (the NFKC one fails exactly the three compatibility-character cases)

## 2. Write the definition down

- [x] 2.1 `.docs/integration-plan.md` §3 definition, ADR 0105 and its index row, `.docs/decisions/README.md`, `.docs/status/scraper.md`, `scraper/CLAUDE.md` pointer if needed

## 3. Closing

- [x] 3.1 Apply iw-docs-update and add the iw-ai-log row
- [x] 3.2 Run iw-pr-review and fix real findings (iw-reviewer on 96146ce..077dfee: no defects; two low doc findings, dispositions in follow-ups.md)
