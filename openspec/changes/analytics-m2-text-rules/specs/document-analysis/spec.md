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
