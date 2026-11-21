## ADDED Requirements

### Requirement: M3 signal semantics
Each M3 signal result SHALL be `fail` when the signal is present, `pass` when absent, `uncertain` when a rule found a candidate only the LLM can confirm, and `not_applicable` when inputs are missing. Without a merged judge verdict, S3.3 and S3.4 SHALL be `uncertain` with the rule candidate as evidence when a candidate exists, and `pass` otherwise. S3.7 (KNF public warnings list) SHALL NOT run while it is not implemented.

#### Scenario: Rules-only candidates
- **WHEN** the mock document `007bbcee…` is analyzed without a judge
- **THEN** S3.3 and S3.4 are `uncertain` with evidence quoted from the text, and no S3.7 result is listed

### Requirement: S3.1 entity not in the registry
S3.1 SHALL be `fail` for every M3 finding (routing sends a publisher that is a registry firm to M2, so the entity behind an M3 offer is never in the registry), quoting `author.handle`, else `author.name`, else the page host from `url`.

#### Scenario: Handle as evidence
- **WHEN** the mock document `cdbf5306…` is analyzed
- **THEN** S3.1 is `fail` with evidence `@sygnaly_vip` from `author.handle`

#### Scenario: Page host as evidence
- **WHEN** the mock document `007bbcee…` is analyzed
- **THEN** S3.1 is `fail` with evidence `zlotykapital-fo.example.com` from `url`

### Requirement: S3.2 advisory-service vocabulary
S3.2 SHALL be `fail` when the text has a term from its PL/EN dictionary (`family office`, `wealth management`, `doradztwo inwestycyjne`, `doradca inwestycyjny`, `zarządzanie portfelem`, `indywidualna strategia`), case-insensitively and on word boundaries, quoting it, and `pass` otherwise.

#### Scenario: Family office offer
- **WHEN** the mock document `007bbcee…` is analyzed
- **THEN** S3.2 is `fail` with evidence `Family Office`

#### Scenario: No service vocabulary
- **WHEN** the mock document `cdbf5306…` is analyzed
- **THEN** S3.2 is `pass`

### Requirement: S3.3 personalization
S3.3 SHALL find candidates from its dictionary (`dopasujemy … do Twojej sytuacji`, `konsultacja 1:1` in any inflection, `profil inwestycyjny`, `ankieta inwestycyjna`, `indywidualnie dobierzemy`, `szyty na miarę`). It carries an `llm:` block and is sent to the LLM whenever it applies.

#### Scenario: Personal consultation
- **WHEN** the mock document `007bbcee…` is analyzed without a judge
- **THEN** S3.3 is `uncertain` with evidence from the text such as `dopasujemy portfel do Twojej sytuacji`

#### Scenario: Mass signals
- **WHEN** the mock document `cdbf5306…` is analyzed without a judge
- **THEN** S3.3 is `pass`

### Requirement: S3.4 recommendation of specific instruments
S3.4 SHALL find a candidate when a recommending buy, sell or hold form (such as `kup`, `kupuj`, `kupno`, `sprzedaj`, `sprzedaż`, `trzymaj`, `rekomendujemy`, `rekomenduję`, `polecam kupić`, `co kupić`, `co sprzedać`) occurs within one sentence of an instrument noun from Art. 2-3 of the Act on Trading in Financial Instruments (`akcje`, `obligacje`, `ETF`, `CFD`, `opcje`, `kontrakty terminowe`, `futures`, `certyfikaty`, `jednostki funduszy`), quoting the sentence with the expression. First-person past forms (`kupiłam`, `sprzedałem`) and negated expressions (`nie udzielamy rekomendacji`, `nie polecamy kupna`) SHALL NOT be candidates. Plain crypto-assets (`bitcoin`, `BTC`, `ethereum`, `ETH`, `kryptowaluty`) SHALL NOT count as instruments; crypto CFDs, futures and options SHALL count, because the derivative noun matches whatever the underlying (Art. 2 lit. h/i). It carries an `llm:` block and is sent to the LLM whenever it applies.

#### Scenario: Buy and sell recommendation
- **WHEN** the mock document `007bbcee…` is analyzed without a judge
- **THEN** S3.4 is `uncertain` with evidence containing `rekomendujemy kupno obligacji`

#### Scenario: Instrument in the previous sentence
- **WHEN** the mock document `cdbf5306…` is analyzed without a judge
- **THEN** S3.4 is `uncertain` with evidence `Codziennie mówię, co kupić, a co sprzedać.`

#### Scenario: Negated recommendation
- **WHEN** the mock document `72acbb3b…` is analyzed without a judge
- **THEN** S3.4 is `pass`

#### Scenario: Personal story is not a recommendation
- **WHEN** the mock document `182e5a42…` (`kupiłam pierwszy ETF`) is evaluated by S3.4
- **THEN** S3.4 is `pass`

#### Scenario: Plain crypto only
- **WHEN** the text is `Kupuj bitcoina teraz, sprzedaj na szczycie.`
- **THEN** S3.4 is `pass`

#### Scenario: Crypto derivative
- **WHEN** the text is `Kupuj CFD na bitcoina, zanim wystrzeli.`
- **THEN** S3.4 is `uncertain` with that sentence as evidence

### Requirement: S3.5 paid model
S3.5 SHALL be `fail` when the text has paid-model vocabulary (`abonament`, `subskrypcja`, `sygnały premium`, `VIP`, `płatna grupa`) or a monthly price (`<amount> zł/mies`, `PLN miesięcznie`), quoting it, and `pass` otherwise.

#### Scenario: Subscription
- **WHEN** the mock document `007bbcee…` is analyzed
- **THEN** S3.5 is `fail` with evidence from `Abonament 990 zł miesięcznie`

#### Scenario: Monthly price
- **WHEN** the mock document `cdbf5306…` is analyzed
- **THEN** S3.5 is `fail`

#### Scenario: Free content
- **WHEN** the mock document `72acbb3b…` is analyzed
- **THEN** S3.5 is `pass`

### Requirement: S3.6 targeting Poland
S3.6 SHALL be `fail` when the text has a `zł`/`PLN` amount or a `+48` phone number (quoting it), else when the page host ends in `.pl` (quoting the host from `url`), else when the language guess is `pl` (null evidence, explanation says Polish language). Otherwise it SHALL be `pass`.

#### Scenario: Price in złoty
- **WHEN** the mock document `007bbcee…` is analyzed
- **THEN** S3.6 is `fail` with evidence containing `zł`

#### Scenario: Polish language only
- **WHEN** the mock document `72acbb3b…` is analyzed
- **THEN** S3.6 is `fail` with null evidence

#### Scenario: English page abroad
- **WHEN** an English page on a `.com` host with no PLN or `+48` is analyzed
- **THEN** S3.6 is `pass`

### Requirement: S3.8 crypto-asset recommendations outside Art. 2
S3.8 SHALL be `fail` when an S3.4 buy, sell or hold form occurs within one sentence of a plain crypto-asset word (`bitcoin`, `BTC`, `ethereum`, `ETH`, `kryptowaluty`, `altcoiny`) and no Art. 2-3 instrument noun is within that window, quoting the sentence, and `pass` otherwise. Its severity is low and its explanation SHALL say the assets are outside Art. 2 ("poza art. 2"). It counts as an advisory signal for routing but SHALL NOT lift the gate.

#### Scenario: Crypto signal group
- **WHEN** an unregistered Polish post says `Kupuj bitcoina teraz, sprzedaj na szczycie. Grupa VIP 99 zł/mies.`
- **THEN** an M3 finding is returned with S3.8 `fail`, S3.4 `pass`, a score of at most 0.4, and a summary saying the assets are outside Art. 2

#### Scenario: Crypto derivative is not S3.8
- **WHEN** the text is `Kupuj CFD na bitcoina, zanim wystrzeli.`
- **THEN** S3.8 is `pass`

### Requirement: M3 score and hard gate
The M3 score SHALL be `σ(bias + Σ wᵢ·xᵢ)` with `bias` and weights from `m3_signals.yaml` (`x` as for M1), rounded to 3 decimals, ranking the Art. 76 elements: personalization together with a recommendation of instruments strongest, a recommendation of instruments alone strong, personalization alone weak, general education low. When S3.4 is neither `fail` nor `uncertain`, the score SHALL be at most 0.4 and the summary SHALL say it was capped. An `uncertain` S3.4 lifts the gate; S3.3 alone SHALL NOT.

#### Scenario: Personalized paid recommendations
- **WHEN** the mock document `007bbcee…` is analyzed without a judge
- **THEN** the score is at least 0.7 (the M3 default threshold)

#### Scenario: Instrument recommendation alone is strong
- **WHEN** a page by an unregistered Polish entity has S3.4 `fail` (from a fake judge) and S3.2, S3.3 and S3.5 `pass`
- **THEN** the score is at least 0.7

#### Scenario: Personalization alone is weak
- **WHEN** a page has S3.3 `fail` and S3.4 `pass`
- **THEN** the score is at most 0.4 and the summary mentions the cap

#### Scenario: Both elements are strongest
- **WHEN** the same page has S3.3 and S3.4 both `fail`
- **THEN** its score is higher than with S3.4 `fail` alone

#### Scenario: Educational article is capped
- **WHEN** the mock document `72acbb3b…` is analyzed
- **THEN** a finding is returned with a score of at most 0.4

#### Scenario: Gate caps strong non-advisory signals
- **WHEN** a page has S3.1, S3.2, S3.5 and S3.6 `fail` and S3.3 and S3.4 `pass`
- **THEN** the score is exactly `min(σ(…), 0.4)` and the summary mentions the cap

#### Scenario: Mass signals without the LLM
- **WHEN** the mock document `cdbf5306…` is analyzed without a judge
- **THEN** the score is above 0.4 and below the score with a judge that confirms S3.4

### Requirement: M3 alongside M1
When a document is routed to M1 and S3.3 or S3.4 is `fail` or `uncertain`, analytics SHALL also emit an M3 finding against the publisher if any sentence holding such a candidate does not name the matched registry firm (its name, core name or alias), because the offer is then the publisher's own. When every such sentence names the firm, the offer is the firm's and analytics SHALL emit no M3 finding. The M3 finding SHALL have `firm: null` and the publisher as `advertiser`.

#### Scenario: Finfluencer's own buy calls
- **WHEN** a Polish `third_party` post by `@trader_ola` says `Konto mam w EuroTrade Markets.` and `Moja grupa: co tydzień mówię, co kupić z akcji WIG20.`
- **THEN** an M1 finding for EuroTrade and an M3 finding with advertiser handle `@trader_ola` and `firm: null` are returned

#### Scenario: The firm's own offer
- **WHEN** a Polish `third_party` post says `Alfa Inwestycje DM rekomenduje kupno obligacji skarbowych.`
- **THEN** only an M1 finding is returned

#### Scenario: Ad without advisory content
- **WHEN** the mock documents `3c41441c…` and `182e5a42…` are analyzed
- **THEN** each returns only an M1 finding

### Requirement: M3 finding assembly
The M3 finding SHALL carry the challenge's M3 output: entity data in `advertiser` (`in_registry` false, `on_warning_list` null), the offer content in `content_excerpt` (at most 500 characters) and the location in `url` and `platform`. It SHALL also have `module` M3, `firm` null, the M3 signal results, the raw `score`, a Polish title that names the advertiser, a Polish summary listing present and uncertain signals and any cap or S3.8 note, `status` new, and `model.llm` null in rules-only mode. It SHALL validate against `contracts/schemas/finding.schema.json` v1.

#### Scenario: Family office finding
- **WHEN** the mock document `007bbcee…` is analyzed
- **THEN** the finding has `firm` null, a title naming the advertiser, and passes `python contracts/validate.py finding`

#### Scenario: CLI over all mocks
- **WHEN** the CLI runs on `contracts/mocks/documents.json`
- **THEN** it exits 0 and its output, holding M1, M2 and M3 findings, passes `python contracts/validate.py finding`
