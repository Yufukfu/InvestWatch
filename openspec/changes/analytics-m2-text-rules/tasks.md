# Tasks

Scope approved by Damian ("dokładamy brakujące reguły, start"). R10 first, then R9; cut R9 per design "Cut plan" if short on time. Tests use the stub judge only and never edit `contracts/mocks/`. Thresholds are not changed here.

## 1. Per-sentence language and R10

- [ ] 1.1 Failing tests (`tests/test_rules_m2_text.py`): `sentence_language` on eurotrade pl / en, `Ryzyko!` and `Reklama.` `None`, sentences and offsets unchanged on the preprocessing fixtures; R10 eurotrade `fail`, bank `pass`, bilingual `pass`, no warning `not_applicable` with "brak informacji o ryzyku", English legal block does not set the main language, unknown language `uncertain`
- [ ] 1.2 `preprocessing.sentence_language`, `rules/m2_text.py` R10, catalogue entry `implemented: true` with the warning aliases, engine import; existing catalogue-list tests updated; tests green
- [ ] 1.3 Mutation check

## 2. R9 comprehensibility (LLM-first)

- [ ] 2.1 Failing tests: jargon warning rules-only `uncertain` naming the hits, plain and CFD warnings `pass` and not deferred, stub-judge `fail` with `Ocena: 1/5` and verified quote → `fail` / `hybrid`, `fail` with `Ocena: 3/5` or no rating → `uncertain`, unverified quote → `uncertain`, no warning `not_applicable`, bad params rejected at load
- [ ] 2.2 `Rule.accept_llm_verdict` hook in `_refine`, R9 class, catalogue entry with params and `llm:` block, new `KNOWN_PARAMS` with validation; tests green
- [ ] 2.3 Mutation check

## 3. Close

- [ ] 3.1 Gold evaluation rules-only before / after (and `--llm` if available); per-rule P/R and M2 at 0.1 in the PR body; `test_eval_thresholds` result reported to the coordinator
- [ ] 3.2 Docs (`.docs/analytics-plan.md` M2 rule list, `.docs/status/` analytics line if present), AI log, `docs-check`
- [ ] 3.3 Archive the change (last commit)
