## MODIFIED Requirements

### Requirement: S1.3 partnership label
S1.3 SHALL record whether a partnership label is present: `fail` when the text has a label from its dictionary (`#reklama`, `#ad`, `#współpraca`, `#sponsored`, `#partner`, `partner reklamowy`, `współpraca reklamowa`, `płatna współpraca`, `materiał sponsorowany`, `sponsorowany`); the bare word `partner` SHALL NOT count, because it is common in neutral text or a link's `rel` contains `sponsored`, quoting the label or the href; `pass` otherwise.

#### Scenario: Hashtag label
- **WHEN** the mock document `182e5a42…` is analyzed
- **THEN** S1.3 is `fail` with evidence `#współpraca`

#### Scenario: No label
- **WHEN** the mock document `3c41441c…` is analyzed
- **THEN** S1.3 is `pass`

#### Scenario: Negated label
- **WHEN** the text is `To nie jest współpraca reklamowa, kupiłem sam.`
- **THEN** S1.3 is `pass`

#### Scenario: Sponsored link
- **WHEN** the text has no label and a link has `rel` `nofollow sponsored`
- **THEN** S1.3 is `fail`

#### Scenario: Missing label does not lower the score
- **WHEN** S1.3 is `pass` on a post
- **THEN** the M1 score equals σ of the bias plus the other signals' terms alone, and adding `#współpraca` to the same post raises it

#### Scenario: Bare partner is not a label
- **WHEN** a Polish third-party post says `Nasz partner biznesowy omawia spotkanie z Alfa Inwestycje DM.`
- **THEN** S1.3 is `pass` and the M1 score is below 0.6

#### Scenario: Partner as an ad label
- **WHEN** a post about Alfa Inwestycje DM says `#partner` or `partner reklamowy`
- **THEN** S1.3 is `fail` quoting that label

#### Scenario: S1.3 partnership label: further obligations
- **WHEN** this requirement is applied
- **THEN** A label negated on the same line SHALL NOT count, as for R2; a hashtag is never negated.
- **AND** A present label SHALL raise the M1 score; a missing label SHALL NOT lower it (it contributes nothing).

### Requirement: S1.7 targeting readers in Poland
S1.7 SHALL be `fail` when the text has a `zł`/`PLN` amount or a `+48` phone number (quoting it), else when the page host ends in `.pl` (quoting the host from `url`), else when the language guess is `pl` (null evidence, explanation says Polish language); otherwise `pass`.

#### Scenario: Złoty amount
- **WHEN** the mock document `3c41441c…` is analyzed
- **THEN** S1.7 is `fail` with evidence containing `zł`

#### Scenario: Polish language only
- **WHEN** the mock document `182e5a42…` is analyzed
- **THEN** S1.7 is `fail` with null evidence

#### Scenario: English ad of a Polish brokerage house
- **WHEN** an English third-party post names Alfa Inwestycje and has no Polish marker
- **THEN** an M1 finding is returned with S1.7 `pass` and no lower certainty than the same post without S1.7

#### Scenario: English ad of a foreign branch
- **WHEN** an English third-party post names EuroTrade (`foreign_branch`) and has no Polish marker
- **THEN** an M1 finding is returned with S1.7 `pass`

#### Scenario: S1.7 targeting readers in Poland: further obligations
- **WHEN** this requirement is applied
- **THEN** For a foreign firm without a Polish branch (`foreign_no_branch`), an M1 candidate with S1.7 `pass` SHALL produce no finding (routing requirement, reason `not_targeting_poland`), so its Polish-language ads are kept and foreign-language ones are not.
- **AND** For a firm registered in Poland (`brokerage_house`, `brokerage_bank`, `foreign_branch`: a branch is registered in Poland), S1.7 SHALL only be recorded as an attribute.

### Requirement: M1 finding assembly
The M1 finding SHALL be an inventory entry with `module` M1, the matched `firm` (firm data, `authorized` true), the `advertiser` (advertiser data), the M1 signal results, the raw `score`, `status` new, `url` and `platform` from the document (location), and `model.llm` null in rules-only mode. Its `content_excerpt` (ad content) SHALL be a window of at most 500 characters around the first evidence found in the text, or the start of the text without one.

#### Scenario: M1 finding assembly: wording and updates
- **WHEN** an M1 finding is built or its document is scanned again
- **THEN** its Polish title names the advertiser and the firm and says "reklamuje" when an ad signal (S1.2, S1.3 or S1.4) is `fail` and "wspomina" otherwise, with "Nieznany autor" when the advertiser has no name
- **AND** its Polish summary says whether a partnership label is present and lists present, uncertain and unchecked signals
- **AND** a re-scan of the same document SHALL update this finding through the worker's upsert, not add another

#### Scenario: Finfluencer finding
- **WHEN** the mock document `3c41441c…` is analyzed
- **THEN** the finding names `@inwestor_jan` or `Jan Inwestor` and `EuroTrade` in its title, has `firm.registry_id` `2d7456b6-…`, its summary says no partnership label was found, and it passes `python contracts/validate.py finding`

#### Scenario: Plain mention
- **WHEN** a Polish third-party post only names Alfa Inwestycje, with no link, label or call to action
- **THEN** the title says `wspomina` and not `reklamuje`

#### Scenario: Excerpt around the evidence
- **WHEN** a long post names Alfa Inwestycje DM only after 2000 characters of other text
- **THEN** `content_excerpt` has at most 500 characters and contains `Alfa Inwestycje DM`

#### Scenario: Social post without an author
- **WHEN** an Instagram post about Alfa Inwestycje DM has no author
- **THEN** the title starts with `Nieznany autor`

#### Scenario: M1 finding assembly: further obligations
- **WHEN** this requirement is applied
- **THEN** It SHALL validate against `contracts/schemas/finding.schema.json` v1.

### Requirement: M1 signal semantics
M1 SHALL inventory ads of registered investment firms published by third parties or private persons (design decisions 4-5). Each M1 signal result SHALL be `fail` when the signal is present, `pass` when it is absent, `uncertain` when a rule found a candidate only the LLM can confirm, and `not_applicable` when the document lacks the inputs to judge it.

#### Scenario: Rules-only S1.5
- **WHEN** the mock document `3c41441c…` is analyzed without a judge
- **THEN** `rules` holds S1.1-S1.7, S1.5 is `uncertain` with null evidence, and the summary names S1.5 as not checked

#### Scenario: M1 signal semantics: further obligations
- **WHEN** this requirement is applied
- **THEN** S1.5 (promotional vs neutral or educational content) has no rule part: without a merged judge verdict it SHALL be `uncertain` with null evidence and an explanation that it needs the language model, and the summary SHALL name it as not checked.
