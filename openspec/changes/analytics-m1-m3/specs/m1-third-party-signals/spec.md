## ADDED Requirements

### Requirement: M1 signal semantics
Each M1 signal result SHALL be `fail` when the signal is present, `pass` when it is absent, `uncertain` when a rule found a candidate only the LLM can confirm, and `not_applicable` when the document lacks the inputs to judge it (design decision 3). S1.5 (promotional vs neutral or educational content) has no rule part: without a merged judge verdict it SHALL be `uncertain` with null evidence and an explanation that it needs the language model, and the summary SHALL name it as not checked.

#### Scenario: Rules-only S1.5
- **WHEN** the mock document `3c41441c…` is analyzed without a judge
- **THEN** `rules` holds S1.1-S1.6, S1.5 is `uncertain` with null evidence, and the summary names S1.5 as not checked

### Requirement: S1.1 mention of a registered firm
S1.1 SHALL be `fail` with the quote of the matched name or alias when the firm was matched by name, `fail` quoting the href when matched by link host, `fail` quoting the page host from `url` when matched by page domain, and `uncertain` with null evidence when matched only fuzzily.

#### Scenario: Name in the caption
- **WHEN** the mock document `3c41441c…` is analyzed
- **THEN** S1.1 is `fail` with evidence `EuroTrade Markets`

#### Scenario: Alias in the caption
- **WHEN** the mock document `182e5a42…` is analyzed
- **THEN** S1.1 is `fail` with evidence `Alfa Inwestycje DM`

#### Scenario: Fuzzy-only match
- **WHEN** a `third_party` post mentions `Alfa Inwestycji` and nothing else of the firm
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
S1.3 SHALL be `fail` when the text has a partnership label from its dictionary (`#reklama`, `#ad`, `#współpraca`, `#sponsored`, `współpraca reklamowa`, `płatna współpraca`, `materiał sponsorowany`, `sponsorowany`, `partner`) or a link's `rel` contains `sponsored`, quoting the label or the href. A label negated on the same line SHALL NOT count, as for R2; a hashtag is never negated. Otherwise S1.3 SHALL be `pass`. A present label raises the M1 score (starting product rule, design Open Question 2).

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

### Requirement: S1.4 call to action
S1.4 SHALL be `fail` when the text has a call-to-action phrase from its dictionary (imperatives such as `otwórz konto`, `załóż konto`, `zarejestruj się`, `odbierz bonus`, `link w bio`, `kliknij`, `dołącz`, `skorzystaj z kodu`), quoting it, and `pass` otherwise. Only a `pass` is sent to the LLM (LLM seam requirement).

#### Scenario: Link in bio
- **WHEN** the mock document `3c41441c…` is analyzed
- **THEN** S1.4 is `fail` with evidence that starts with `link w bio`

#### Scenario: Past tense is not a call to action
- **WHEN** the mock document `182e5a42…` (`jak założyłam rachunek`) is analyzed
- **THEN** S1.4 is `pass`

### Requirement: S1.6 author other than the firm
S1.6 SHALL be `pass` when the author's profile host or the page host is a domain of the matched firm, or the normalized author handle equals a normalized name, core or alias of the firm. It SHALL be `fail` otherwise, quoting `author.handle`, else `author.name`, else the page host from `url`. It SHALL be `not_applicable` when there is no author and the page host is a social platform.

#### Scenario: Finfluencer handle
- **WHEN** the mock document `3c41441c…` is analyzed
- **THEN** S1.6 is `fail` with evidence `@inwestor_jan` from `author.handle`

#### Scenario: Firm's own account marked third-party
- **WHEN** a `third_party` post names Alfa Inwestycje and its author has handle `@alfa_inwestycje`
- **THEN** S1.6 is `pass`

#### Scenario: Social post without author
- **WHEN** an Instagram `third_party` post names a firm and has no `author`
- **THEN** S1.6 is `not_applicable`

### Requirement: M1 score
The M1 score SHALL be `σ(bias + Σ wᵢ·xᵢ)` with `bias` and weights from `m1_signals.yaml`, `x = 1` for `fail`, `0.5` for `uncertain`, `0` otherwise, rounded to 3 decimals and always in 0-1.

#### Scenario: Affiliate post scores high
- **WHEN** the mock document `3c41441c…` is analyzed without a judge
- **THEN** the score is at least 0.6 (the M1 default threshold)

#### Scenario: Labeled cooperation scores lower
- **WHEN** the mock documents `182e5a42…` and `3c41441c…` are analyzed without a judge
- **THEN** the score of `182e5a42…` is lower than that of `3c41441c…`

#### Scenario: Formula
- **WHEN** a catalogue has bias −1 and one signal of weight 2 that is `uncertain`
- **THEN** the score is σ(0) = 0.5

### Requirement: M1 finding assembly
The M1 finding SHALL have `module` M1, the matched `firm` (`authorized` true), the `advertiser`, the M1 signal results, the raw `score`, a Polish title that names the advertiser and the firm, a Polish summary listing present, uncertain and unchecked signals, `status` new, `url` and `platform` from the document, `content_excerpt` of at most 500 characters, and `model.llm` null in rules-only mode. It SHALL validate against `contracts/schemas/finding.schema.json` v1.

#### Scenario: Finfluencer finding
- **WHEN** the mock document `3c41441c…` is analyzed
- **THEN** the finding names `@inwestor_jan` or `Jan Inwestor` and `EuroTrade` in its title, has `firm.registry_id` `2d7456b6-…` and passes `python contracts/validate.py finding`
