# Proposal

## Why

M2 checks firms' own marketing against the 18 UKNF ZASÓB criteria (art. 44 of Delegated Regulation 2017/565). `main` implements 12 of them. Two of the missing ones are text rules that need no scraper `blocks`:

- **R10 Spójność językowa** (lit. f). ZASÓB: "Weryfikuje, czy informacje o ryzyku nie są podane w innym języku niż główny przekaz materiału". It was specified in `analytics-llm-p0` task group 11 and cut for time (follow-up R67).
- **R9 Zrozumiałość dla grupy docelowej** (lit. d). ZASÓB: "Ocenia, czy ostrzeżenie o ryzyku jest przedstawione językiem zrozumiałym dla przeciętnego odbiorcy grupy docelowej". `analytics-m2-p1-rules` left it for an LLM-first change.

The gold set already labels both rules. Damian approved the scope ("dokładamy brakujące reguły, start").

## What Changes

- **Preprocessing:** an additive per-sentence language guess, `sentence_language(text)`. It returns `pl`, `en` or `None` when the signal is under a minimum. Sentences, their offsets and the document guess do not change.
- **R10 (rules-only):** the main language comes from the visible non-`footer`, non-`legal`, non-warning blocks when the document has `blocks`, and otherwise from the non-warning sentences. The fallback is the document guess. R10 is:
  - `fail` when the risk warnings are all in another language;
  - `pass` when at least one warning is in the main language;
  - `uncertain` when the language is unknown;
  - `not_applicable` with "brak informacji o ryzyku" when there is no warning.
- **R9 (LLM-first):**
  - The rules measure a signal on the risk-warning sentences: average sentence length in words, hits from a jargon list, and the jargon share. A raised signal gives `uncertain`, with the numbers in the explanation and the most jargon-heavy warning as evidence. No signal gives `pass`.
  - An `llm:` block (`when: uncertain`) asks for a 1-5 comprehensibility rating and a quoted sentence.
  - R9 is `fail` only when the model rates it 2 or lower and its quote is verified. Without the LLM it stays `uncertain`.
- **Engine seam (additive):** `Rule.accept_llm_verdict` lets a rule narrow an LLM verdict before it replaces the rules-only result. R9 uses it to enforce the rating. The default changes nothing.
- **Catalogue:** R9 and R10 become `implemented: true`, with new params. Their classes live in a new module, `rules/m2_text.py`, to stay clear of the parallel visual-rules change (`rules/m2_visual.py`).

**Out of scope:** the visual rules R5, R7, R8 and R13 (parallel change), the default thresholds (branch `analytics-deepseek-default`), and the LLM client, prompt and cache.

## Capabilities

### Modified Capabilities

- `m2-compliance-rules`: the catalogue implements R9 and R10, and R9 has an `llm:` block. New requirements cover R10 and R9.
- `document-analysis`: preprocessing adds a per-sentence language guess.

## Impact

- Code: `analytics/src/investwatch_analytics/preprocessing.py` (one function), `rules/m2_text.py` (new), `rules/engine.py` (import, params, one hook), `rules/m2_rules.yaml` (R9 and R10 entries only).
- Tests: new `tests/test_rules_m2_text.py`, plus updated catalogue lists in the existing tests.
- M2 scores: R9 and R10 are low severity (weight 1). Re-check `eval/thresholds.json` with `eval/run.py`.
