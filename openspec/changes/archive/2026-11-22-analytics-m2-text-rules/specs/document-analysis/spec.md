## ADDED Requirements

### Requirement: Per-sentence language guess
Preprocessing SHALL offer a language guess for one sentence: `pl`, `en`, or `None` when the stronger language has fewer than 2 marker points or the two languages tie. Polish points are Polish marker words plus words with a Polish diacritic; English points are English marker words. The guess SHALL be additive: sentence splitting, sentence offsets and the document-level language guess SHALL NOT change.

#### Scenario: Polish and English sentences
- **WHEN** the sentences of the `eurotrade` text are guessed
- **THEN** `Nasi klienci zarobili średnio 34% w 2025 roku.` is `pl` and `Risk warning: CFDs are complex instruments and come with a high risk of losing money rapidly due to leverage.` is `en`

#### Scenario: Too little signal
- **WHEN** the sentence is `Ryzyko!` or `Reklama.`
- **THEN** the guess is `None`

#### Scenario: Sentences unchanged
- **WHEN** the existing preprocessing fixtures are split before and after this change
- **THEN** the sentences, their `start` and `end` offsets and the document guess are identical

### Requirement: Evidence-free uncertain results are not scored
The M2 score SHALL leave out a rules-only `uncertain` result (`method` `rule`) of a rule whose catalogue entry sets `llm_only_uncertain: true`, from both the weighted failures and the applicable weight. The finding SHALL still list the result. An `uncertain` decided by the LLM, and every `fail` and `pass`, SHALL be scored as before. `llm_only_uncertain` SHALL be a boolean and is checked at load.

#### Scenario: Rules-only R9 uncertain
- **WHEN** R9 is `uncertain` from the rules only (a jargon-heavy warning, no LLM)
- **THEN** the M2 score equals the score of the same results without R9, and R9 is still in `rules[]`

#### Scenario: LLM verdict for R9
- **WHEN** the LLM fails R9 with `Ocena: 1/5` and a verified quote, or answers `uncertain`
- **THEN** R9 is scored like any other rule result

#### Scenario: Other rules unaffected
- **WHEN** R2 is `uncertain` from the rules only
- **THEN** it counts as half a failure, as before

