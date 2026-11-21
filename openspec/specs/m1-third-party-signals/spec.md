# m1-third-party-signals Specification

## Purpose
Inventory ads of registered investment firms published by third parties or private persons (UKNF module M1): firm data, advertiser data, ad content and URL, with a rules-only score of how certain each entry is a third-party ad of that firm.

## Requirements

### Requirement: M1 signal semantics
M1 SHALL inventory ads of registered investment firms published by third parties or private persons (design decisions 4-5). Each M1 signal result SHALL be `fail` when the signal is present, `pass` when it is absent, `uncertain` when a rule found a candidate only the LLM can confirm, and `not_applicable` when the document lacks the inputs to judge it.

#### Scenario: Rules-only S1.5
- **WHEN** the mock document `3c41441c…` is analyzed without a judge
- **THEN** `rules` holds S1.1-S1.7, S1.5 is `uncertain` with null evidence, and the summary names S1.5 as not checked

#### Scenario: M1 signal semantics: further obligations
- **WHEN** this requirement is applied
- **THEN** S1.5 (promotional vs neutral or educational content) has no rule part: without a merged judge verdict it SHALL be `uncertain` with null evidence and an explanation that it needs the language model, and the summary SHALL name it as not checked.

### Requirement: S1.1 mention of a registered firm
S1.1 SHALL be `fail` with the quote of the matched name or alias when the firm was matched by name, `fail` quoting the href when matched by link host, and `uncertain` with null evidence when matched only fuzzily.

#### Scenario: Name in the caption
- **WHEN** the mock document `3c41441c…` is analyzed
- **THEN** S1.1 is `fail` with evidence `EuroTrade Markets`

#### Scenario: Alias in the caption
- **WHEN** the mock document `182e5a42…` is analyzed
- **THEN** S1.1 is `fail` with evidence `Alfa Inwestycje DM`

#### Scenario: Fuzzy-only match
- **WHEN** a Polish `third_party` post mentions `Alfa Inwestycji` and nothing else of the firm
- **THEN** S1.1 is `uncertain` with null evidence

### Requirement: S1.2 affiliate link or promo code
S1.2 SHALL be `fail` when a link's query string has a referral key (`ref`, `aff`, `affiliate`, `partner`, `promo`, `coupon`, `referral`) or the text has a referral phrase (`kod polecający`, `kod promocyjny`, `z moim linkiem`, `z kodem`), quoting the href part or the phrase. A link whose only tracking is `utm_*` SHALL give `uncertain`. Without either it SHALL be `pass`. Malformed hrefs SHALL be skipped.

#### Scenario: Referral link
- **WHEN** the mock document `3c41441c…` is analyzed
- **THEN** S1.2 is `fail` with evidence that contains `ref=JAN500` and is a substring of the link href

#### Scenario: Only UTM parameters
- **WHEN** the only link is `https://alfa-inwestycje.example.com/?utm_source=ig`
- **THEN** S1.2 is `uncertain`

#### Scenario: No referral
- **WHEN** the mock document `182e5a42…` is analyzed
- **THEN** S1.2 is `pass`

#### Scenario: Word inside another word
- **WHEN** the text contains `preferencje` and no link
- **THEN** S1.2 is `pass`

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

### Requirement: S1.4 call to action
S1.4 SHALL be `fail` when the text has a call-to-action phrase from its dictionary (imperatives such as `otwórz konto`, `załóż konto`, `zarejestruj się`, `odbierz bonus`, `link w bio`, `kliknij`, `dołącz`, `skorzystaj z kodu`), quoting it, and `pass` otherwise. It carries an `llm:` block, and its `ask_llm` hook SHALL ask the LLM only about a `pass`, so the LLM can add an implicit call to action but never remove a dictionary hit.

#### Scenario: Link in bio
- **WHEN** the mock document `3c41441c…` is analyzed
- **THEN** S1.4 is `fail` with evidence that starts with `link w bio`

#### Scenario: Only a pass goes to the LLM
- **WHEN** S1.4's `ask_llm` hook is given a `pass` and then a `fail` result
- **THEN** it answers true for the `pass` and false for the `fail`

#### Scenario: Past tense is not a call to action
- **WHEN** the mock document `182e5a42…` (`jak założyłam rachunek`) is analyzed
- **THEN** S1.4 is `pass`

### Requirement: S1.6 author other than the firm
S1.6 SHALL be `fail` on every M1 finding that has an author or a non-social page host, quoting `author.handle`, else `author.name`, else the page host from `url` (a publisher that is the firm is routed to M2, never to M1). When the author handle equals the matched firm's name but no domain proves the account is the firm's, S1.6 SHALL be `uncertain`, quoting the handle. It SHALL be `not_applicable` when there is no author and the page host is a social platform.

#### Scenario: Finfluencer handle
- **WHEN** the mock document `3c41441c…` is analyzed
- **THEN** S1.6 is `fail` with evidence `@inwestor_jan` from `author.handle`

#### Scenario: Social post without author
- **WHEN** a Polish Instagram `third_party` post names a firm and has no `author`
- **THEN** S1.6 is `not_applicable`

#### Scenario: Handle like the firm's name
- **WHEN** a third-party post about Alfa Inwestycje is by `@alfainwestycje` and nothing on the firm's domain backs it
- **THEN** S1.6 is `uncertain` with evidence `@alfainwestycje` and an explanation that the account is not confirmed as the firm's

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

### Requirement: M1 score
The M1 score SHALL express how certain it is that the document is a third-party ad of the matched registered firm. It SHALL be `σ(bias + Σ wᵢ·xᵢ)` with `bias` and weights from `m1_signals.yaml`, `x = 1` for `fail`, `0.5` for `uncertain`, `0` otherwise, rounded to 3 decimals and always in 0-1.

#### Scenario: Affiliate post
- **WHEN** the mock document `3c41441c…` is analyzed without a judge
- **THEN** the score is at least 0.6 (the M1 default threshold)

#### Scenario: Labeled cooperation
- **WHEN** the mock document `182e5a42…` is analyzed without a judge
- **THEN** the score is at least 0.6

#### Scenario: Bare mention
- **WHEN** a Polish third-party post only names Alfa Inwestycje, with no link, label or call to action
- **THEN** a finding is returned with a score below 0.6

#### Scenario: Formula
- **WHEN** a catalogue has bias −1 and one signal of weight 2 that is `uncertain`
- **THEN** the score is σ(0) = 0.5

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
