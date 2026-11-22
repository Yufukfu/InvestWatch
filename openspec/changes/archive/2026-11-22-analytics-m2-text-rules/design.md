# Design

## Context

- **On `main`:**
  - the rule engine (`rules/engine.py`) with `llm:` blocks, `Rule.ask_llm` and `_refine`;
  - the shared risk-warning detector `_RiskWarnings` in `rules/m2.py` (R4, R6), with R3's patterns reused through YAML anchors;
  - `preprocessing.py`, which makes one language guess per document (`guess_language`, `pl`/`en`).
- **ZASÓB** (`doc/ZASÓB …docx`):
  - R9: "Ocenia, czy ostrzeżenie o ryzyku jest przedstawione językiem zrozumiałym dla przeciętnego odbiorcy grupy docelowej".
  - R10: "Weryfikuje, czy informacje o ryzyku nie są podane w innym języku niż główny przekaz materiału".
- **The cut R10 design:** `analytics-llm-p0` design §"R10 language consistency" and task group 11. This change reuses that design and its scenarios.
- **A parallel change** adds R5, R7, R8 and R13 in `rules/m2_visual.py`. Branch `analytics-deepseek-default` changes the default thresholds.

## Decisions

### 1. A new module, minimal shared edits

R9 and R10 live in `rules/m2_text.py` and subclass `_RiskWarnings` from `rules/m2.py`, so they share the definition of a warning with R3, R4 and R6. `Catalogue.load` imports the module.

`m2.py` is not edited. `engine.py` gains:
- the import;
- the new `KNOWN_PARAMS` keys and their validation;
- one hook.

### 2. Per-sentence language guess (additive)

`preprocessing.sentence_language(text) -> "pl" | "en" | None` uses the same marker words and Polish diacritics as the document guess.
- **Scores:** `pl` is the number of Polish marker words plus the number of words that contain a Polish diacritic. `en` is the number of English marker words.
- **Result:** the winner when its score is at least `MIN_LANGUAGE_SIGNAL = 2` and strictly greater than the other score. Otherwise `None`, so `Ryzyko!` and `Reklama.` are `None`.

`Sentence`, `split_sentences`, `Preprocessed` and `guess_language` are unchanged. The new function is a separate entry point that R10 calls per sentence. A test pins identical sentences and offsets on the existing fixtures.

The guesser stays heuristic. `lingua` was rejected in llm-p0 because the rule needs only pl versus en.

### 3. R10

- **Warnings:** sentences that `_RiskWarnings.is_warning` accepts. With none, R10 is `not_applicable` with `NO_RISK_INFO` ("brak informacji o ryzyku"), so R3 carries the missing warning.
- **Main language:**
  - With `blocks`, it is the length-weighted majority of `sentence_language(block.text)` over the visible blocks of the `desktop` viewport (otherwise the first viewport present). Blocks whose `region` is `footer` or `legal`, and blocks that are warnings, are left out. An English legal block therefore never sets the main language.
  - Without `blocks`, it is the length-weighted majority over the non-warning sentences with a known language.
  - The fallback is the document guess (`ctx.pre.lang`).
- **Verdict:**
  - `pass` when at least one warning is in the main language. The evidence is that warning. A Polish warning next to an extra English one passes.
  - `fail` when every warning has a known language and none is the main language. The evidence is the first warning.
  - `uncertain` otherwise: some warning has an unknown language and none is in the main language, or the main language is unknown.
- Rules-only, no `llm:` block. Severity `low`.

### 4. R9: rules signal, then the LLM

**Rules signal** (params in the catalogue):
- `jargon_patterns` is a list of specialist terms, for example `implik…`, `asymetryczn…`, `zmienność implikowana`, `kontrahent…`, `deprecjacj…`, `partycypacj…`, `ryzyko bazowe`, `wolatyln…`, `derywat…`, `instrument bazowy`, `profil wypłaty`, `duracj…`, `kontango`, `margin call`.
- Over the warning sentences, the rule measures:
  - the average sentence length in words;
  - the jargon hits;
  - the jargon share (hits per word).
- It raises the signal when the average length exceeds `max_avg_sentence_words` (30), or the jargon share is at least `max_jargon_share` (0.05), or there are at least `min_jargon_hits` (2) hits.
- **Results:**
  - Raised gives `uncertain`. The evidence is the warning with the most jargon hits (the first on a tie), and the explanation states the three numbers.
  - Not raised gives `pass`. The evidence is the first warning, and the explanation gives the numbers.
  - With no warning, R9 is `not_applicable` with `NO_RISK_INFO`.
  - Rules-only R9 never fails.

These are catalogue params of one rule, not module thresholds. ADR 0316 defaults are not touched.

**LLM** (`llm: when: uncertain`): the question asks for a 1-5 rating of how comprehensible the warning is to an average retail client. The model starts its explanation with `Ocena: N/5` and quotes the least comprehensible warning sentence verbatim. It answers `fail` for N ≤ 2, `pass` for N ≥ 4, and `uncertain` for 3.

**Enforcement** (engine hook): `Rule.accept_llm_verdict(verdict) -> verdict`. The default returns the verdict unchanged. `_refine` calls it before it merges the verdict. R9's override:
- keeps `fail` only when the explanation holds `Ocena: N/5` with N ≤ 2 (the judge has already required a verified quote for `fail`);
- keeps `pass` only with N ≥ 4;
- turns anything else into `uncertain`, with the model's explanation kept.

A model that says `fail` without a rating, or with a rating of 3, is therefore never a violation.

### 5. A rules-only R9 `uncertain` is not scored (Damian)

The first gold run with R9 moved the rules-only best M2 threshold from 0.1 to 0.05 (follow-ups F2). Damian decided that a rules-only R9 `uncertain` must not raise the M2 score: it has no evidence of an infringement, so only an LLM verdict for R9 counts. The finding still lists it as `uncertain` ("do weryfikacji") with its signal.

- **Where:** a catalogue-level, per-rule flag, `llm_only_uncertain: true`, read into `RuleSpec`. It is validated as a boolean at load. It is not a special case inside R9.
- **How:** `modules/m2.score(rules, catalogue)` leaves out entirely (numerator and denominator) a result that is `uncertain`, has `method` `rule`, and comes from a flagged rule. The rule then weighs as if it were not applicable. An LLM `uncertain` (`hybrid`/`llm`), a `fail` and a `pass` still count. Without the catalogue, `score(rules)` behaves as before.
- **Why leave it out instead of counting it as `pass`:** adding weight to the denominator would lower the score of every document with a jargon-heavy warning. Nothing is known either way, so the result is not scored.

With the flag, rules-only M2 at 0.1 is back to the R10 numbers, and `test_eval_thresholds` stays at 0.1.

### 6. Evaluation

Gold rows already label R9 and R10. Run `eval/run.py --module M2` before and after. If `test_eval_thresholds` fails, report the numbers to the coordinator and do not change the defaults (the deepseek branch owns them).

## Risks

- **Short Polish headlines** without marker words have no language. They drop out of the main language, and the document guess is the fallback.
- **The R9 jargon list is incomplete.** Lawful ESMA CFD warnings must pass, and a test pins this.
- **The `Rule catalogue` requirement is modified** by this change and by the visual change. Whichever is archived second reconciles the implemented and LLM lists.

## Cut plan

If time runs short, ship R10 only. R9 stays `implemented: false` and gets a row in `follow-ups.md`.
