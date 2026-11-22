# Tasks

Scope approved by Damian ("dokładamy brakujące reguły, start"). R10 first, then R9; cut R9 per design "Cut plan" if short on time. Tests use the stub judge only and never edit `contracts/mocks/`. Thresholds are not changed here.

## 1. Per-sentence language and R10

- [x] 1.1 Failing tests (`tests/test_rules_m2_text.py`): `sentence_language` on eurotrade pl / en, `Ryzyko!` and `Reklama.` `None`, sentences and offsets unchanged on the preprocessing fixtures; R10 eurotrade `fail`, bank `pass`, bilingual `pass`, no warning `not_applicable` with "brak informacji o ryzyku", English legal block does not set the main language, unknown language `uncertain`
- [x] 1.2 `preprocessing.sentence_language`, `rules/m2_text.py` R10, catalogue entry `implemented: true` with the warning aliases, engine import; existing catalogue-list tests updated; tests green
- [x] 1.3 Mutation check. `mutations: 13 tried, 13 caught` (visible filter, footer/legal exclusion, warning blocks excluded, first viewport only, length weighting, block→sentence and sentence→document-guess fallbacks, warnings excluded from the sentence majority, unknown-language uncertain, no-warning branch, minimum signal 2→3, tie → None, diacritic words). The tie test first used a 1:1 tie under the minimum and let the tie mutant survive; it now uses 2:2. Gold rules-only: R10 strict P/R 1.0/1.0 (1 fail, 6 pass); M2 at 0.1 F1 0.829 → 0.857, recommended threshold unchanged (0.1)

## 2. R9 comprehensibility (LLM-first)

- [x] 2.1 Failing tests: jargon warning rules-only `uncertain` naming the hits, plain and CFD warnings `pass` and not deferred, stub-judge `fail` with `Ocena: 1/5` and verified quote → `fail` / `hybrid`, `fail` with `Ocena: 3/5` or no rating → `uncertain`, unverified quote → `uncertain`, no warning `not_applicable`, bad params rejected at load
- [x] 2.2 `Rule.accept_llm_verdict` hook in `_refine`, R9 class, catalogue entry with params and `llm:` block, new `KNOWN_PARAMS` with validation; tests green
- [x] 2.3 Mutation check. `mutations: 16 tried, 16 caught` (each of the three signal conditions, pass when raised, worst-warning evidence, no-warning branch, fail rating boundary both ways, fail without a rating, pass rating boundary, narrowing removed, rating regex digit range, hook not called, default hook narrowing other rules, positive-integer and share-range param checks). The first run left 2 survivors (worst-warning evidence, the rating regex); a two-warning test and an `Ocena: 1/3` case were added. Gold rules-only: R9 strict P/R 1.0/0.0 (never fails without the LLM, by design), review P/R 1.0/1.0; M2 at 0.1 unchanged at F1 0.857, but the best F1 moves to 0.884 at 0.05 (follow-ups F2)

## 3. Rules-only R9 uncertain is not scored (Damian)

- [x] 3.1 Failing tests: the flag is declared on R9 only and validated as a boolean; a rules-only R9 `uncertain` leaves the score unchanged; an LLM `fail` and an LLM `uncertain` are scored; a rules-only R9 `pass` and R2's `uncertain` are scored as before
- [x] 3.2 `RuleSpec.llm_only_uncertain`, load validation, `modules/m2.score(rules, catalogue)`, R9 `llm_only_uncertain: true`; tests green, `test_eval_thresholds` green at 0.1
- [x] 3.3 Mutation check. `mutations: 8 tried, 8 caught` (flag ignored, method check, result check, flag on every rule, finding scored without the catalogue, flag not read from YAML, boolean validation, R9 flag off). The first run left 2 survivors (method check, result check): the score assertions compared against a pass, not the no-catalogue score; they now assert equality with `score(rules)`, and a rules-only R9 `pass` case was added

## 4. Close

- [x] 4.1 Gold evaluation: rules-only M2 at 0.1 went from F1 0.829 (P 0.944, R 0.739) on `main` to 0.857 (P 0.947, R 0.783), and the recommended threshold stays 0.1 (`test_eval_thresholds` green). With DeepSeek Flash, M2 at 0.1 has F1 0.884 (P 0.95, R 0.826). R9 strict P/R: 1.0/0.0 rules-only, 1.0/1.0 with the LLM. R10: 1.0/1.0 on both runs. The numbers were reported to the coordinator
- [x] 4.2 Docs (`.docs/analytics-plan.md` M2 rule list, `.docs/status/` analytics line if present), AI log, `docs-check`
- [x] 4.3 Archive the change (last commit)
