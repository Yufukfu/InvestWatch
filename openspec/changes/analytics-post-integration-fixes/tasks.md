# Tasks

Each group is one commit, and its first task is the failing test. No test calls a real LLM. Only task 4.1 makes live calls, and it is a measurement, not a test.

## 1. Official sources are not advertisers (~45 min)

- [ ] 1.1 Failing tests: the KNF warnings page (`third_party`, `www.knf.gov.pl`, names EuroTrade and an unregistered adviser) gives no finding, logs `official_source`, and makes no judge call; `uknf.gov.pl`, `sub.gov.pl`, a `firm_own` page and an `unknown` page on `gov.pl` give no module; look-alikes `knf.gov.pl.example.com` and `fakeknf-gov.pl` are routed as usual; an author `profile_url` on `knf.gov.pl` is official; a link to `knf.gov.pl` from a finfluencer post is not; `OFFICIAL_SOURCE_DOMAINS` replaces the default, and a bad entry raises `ConfigError` naming the variable
- [ ] 1.2 `config.official_source_domains()`, the check in `route()`, and `.env.example`; tests green
- [ ] 1.3 Mutation check

## 2. M3 needs an offer signal (~30 min)

- [ ] 2.1 Failing tests: an EY-like page (`unknown`, Polish host, only `family office` and `doradztwo inwestycyjne`) and the mock `72acbb3b…` give no finding and log `no_signals`; S3.3, S3.4, S3.5 and S3.8 each, `fail` or `uncertain`, still give a finding; S3.2 `uncertain` alone does not (`test_has_advisory` is changed for this, as the spec delta says)
- [ ] 2.2 `m3.ADVISORY` without S3.2 (renamed `OFFER`, with the alias kept); tests green; `test_eval_thresholds` still green (defaults unchanged)
- [ ] 2.3 Mutation check

## 3. NFKC once (~30 min)

- [ ] 3.1 Failing tests: `unicodedata.normalize` is called exactly once per `preprocess`; equivalence with the field-by-field functions on every mock and on 200 seeded random texts; linear growth on 100k against 400k `ﬁ`
- [ ] 3.2 `preprocess` normalizes once, through private helpers for the hash and the language; tests green
- [ ] 3.3 Mutation check

## 4. Evaluation with the LLM (~1 h, mostly waiting)

- [ ] 4.1 `eval/run.py --llm` with hosted Gemma 4 (`gemma-4-31b-it`, or `gemma-4-26b-a4b-it` on repeated 503; record which); the key is never printed
- [ ] 4.2 Per module: P/R/F1 at the defaults, the best-F1 threshold, the plateau and the number of cases, sent to the coordinator; defaults unchanged

## 5. Closing

- [ ] 5.1 Docs (`iw-docs-update`): analytics plan §6, `.env.example`, the domain status file, `docs-check` clean
- [ ] 5.2 AI log row (`iw-ai-log`)
- [ ] 5.3 Final review (`iw-pr-review`)
- [ ] 5.4 Archive the change (last commit)
