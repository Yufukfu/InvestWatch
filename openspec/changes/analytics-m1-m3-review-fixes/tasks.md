# Tasks

Kacper's review of PR #35 (6da4f1f). Branch `analytics/analytics-m1-m3` (pushed: merge only, never rebase). `contracts/`, `contracts/mock-server/` and the `web/` mock mode stay untouched.

## 1. Registry wording and legal bases (items 2, 9)

- [x] 1.1 Failing tests: `Registry.demo` true for the bundled seed and false when firms have a `source_url`; the S3.1 explanation and the M3 summary say `nie znaleziono w załadowanym rejestrze firm`, with `(dane demonstracyjne)` only for the demo registry; the M3 title never says "spoza rejestru"; S3.1 has no legal basis; S3.3/S3.4 cite art. 76 and S3.8 art. 2 (Topic 3 annex); the crypto note reads "kryptoaktywa nie są wymienione w katalogu z art. 2 u.o.i.f. (załącznik do tematu 3)"
- [x] 1.2 `registry.py` (`demo`), `rules/m3.py`, `modules/m3.py`, `rules/m3_signals.yaml`, `analytics/registry/README.md`; tests green
- [x] 1.3 Mutation check; `mutations: 7 tried, 7 caught`

## 2. S1.3 labels and the advertiser on social hosts (items 3, 4)

- [x] 2.1 Failing tests: Kacper's sentence `Nasz partner biznesowy omawia spotkanie z Alfa Inwestycje DM.` gives S1.3 `pass` and a score below 0.6; `#partner` and `partner reklamowy` count; an Instagram post without an author gives `advertiser.name`/`website` null and an M1 title starting `Nieznany autor`
- [x] 2.2 `rules/m1_signals.yaml`, `modules/advertiser.py`; tests green
- [x] 2.3 Mutation check; `mutations: 5 tried, 5 caught` (one first survivor, `website` on a web page with an author, got its own test)

## 3. M3 vocabulary and the Polish-marker filter (items 5, 6)

- [x] 3.1 Failing tests: the four new S3.2 terms; English monthly prices for S3.5; Kacper's English example gives an M3 finding; a `foreign_no_branch` firm's English ad gives no finding, a `foreign_branch` one gives M1; `test_redos.py` covers every new pattern
- [x] 3.2 `rules/m3_signals.yaml`, `pipeline.py` (`FOREIGN_TYPES`), `registry/seed.csv` (one fictional `foreign_no_branch` firm); tests green
- [x] 3.3 Mutation check; `mutations: 11 tried, 11 caught`

## 4. Titles, notes and the excerpt (items 7, 8, 10)

- [x] 4.1 Failing tests: M3 titles say `możliwe …` while the deciding signal is `uncertain`; M1 titles say `wspomina` without an ad signal; the M3 summary says personalisation is unconfirmed when S3.3 is `pass`; M1/M3 `content_excerpt` is at most 500 characters around the first evidence
- [x] 4.2 `modules/m1.py`, `modules/m3.py`, `modules/excerpt.py`; tests green
- [x] 4.3 Mutation check; `mutations: 11 tried, 10 caught`, 1 equivalent (counting a `pass` evidence: no rule returns one today; kept for LLM `pass` verdicts with a quote); the first survivor, the earliest of two evidences, got its own test

## 5. Docs and ADR (items 1, 8, 11)

- [x] 5.1 ADR 0308 (the S3.4 gate as a deliberate "may indicate" choice, personalisation unconfirmed) and its row in `.docs/decisions/README.md`; privacy line in `analytics/README.md`; M1/M3 row in `.docs/INDEX.md`; `follow-ups.md` row linking #26's `_BOUNDARY` fix; `docs-check` clean
- [x] 5.2 Mutation check; `mutations: n/a, docs-only`

## 6. Closing

- [ ] 6.1 Apply the iw-docs-update skill (your own `.docs/status/platform.md` `### analytics` line, ADRs) and add the iw-ai-log row
- [ ] 6.2 Run the iw-pr-review skill and fix real findings
