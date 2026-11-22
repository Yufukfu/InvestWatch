# m3-unauthorized-advice-signals Specification

## Purpose
Flag offers by entities outside the KNF registry that may indicate investment advice (Art. 76 of the Act on Trading in Financial Instruments: a recommendation concerning financial instruments, based on the client's situation), with entity data, offer content and URL, rules-only until the LLM confirms the semantic signals.
## Requirements
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

#### Scenario: Demonstration registry
- **WHEN** the mock document `007bbcee…` is analyzed with the bundled seed registry
- **THEN** the S3.1 explanation and the summary contain `nie znaleziono w załadowanym rejestrze firm` and `(dane demonstracyjne)`

#### Scenario: Real registry
- **WHEN** the same document is analyzed with a registry whose firms have a `source_url`
- **THEN** the S3.1 explanation and the summary contain `nie znaleziono w załadowanym rejestrze firm` and not `dane demonstracyjne`

#### Scenario: S3.1 entity not in the registry: further obligations
- **WHEN** this requirement is applied
- **THEN** Its explanation SHALL say the entity was not found in the loaded firm registry ("nie znaleziono w załadowanym rejestrze firm"), never that it is outside the KNF register as a fact, and SHALL add "(dane demonstracyjne)" while the loaded registry is the bundled demonstration data.
- **AND** The registry loader SHALL mark a registry as demonstration data when none of its firms has a `source_url` (the real KNF loader sets one per firm).
- **AND** S3.1 SHALL have no legal basis.

### Requirement: S3.2 advisory-service vocabulary
S3.2 SHALL be `fail` when the text has a term from its PL/EN dictionary (`family office`, `wealth management`, `wealth advisory`, `investment consulting`, `investment advice`, `doradztwo inwestycyjne`, `doradztwo finansowe`, `doradca inwestycyjny`, `zarządzanie portfelem`, `zarządzanie majątkiem`, `indywidualna strategia`), case-insensitively and on word boundaries, quoting it, and `pass` otherwise.

#### Scenario: Family office offer
- **WHEN** the mock document `007bbcee…` is analyzed
- **THEN** S3.2 is `fail` with evidence `Family Office`

#### Scenario: No service vocabulary
- **WHEN** the mock document `cdbf5306…` is analyzed
- **THEN** S3.2 is `pass`

#### Scenario: Challenge vocabulary
- **WHEN** the text uses `investment consulting`, `wealth advisory`, `doradztwo finansowe` or `zarządzanie majątkiem`
- **THEN** S3.2 is `fail` quoting it

### Requirement: S3.3 personalization
S3.3 SHALL find candidates from its dictionary (`dopasujemy … do Twojej sytuacji`, `konsultacja 1:1` in any inflection, `profil inwestycyjny`, `ankieta inwestycyjna`, `indywidualnie dobierzemy`, `szyty na miarę`). It carries an `llm:` block and is sent to the LLM whenever it applies.

#### Scenario: Personal consultation
- **WHEN** the mock document `007bbcee…` is analyzed without a judge
- **THEN** S3.3 is `uncertain` with evidence from the text such as `dopasujemy portfel do Twojej sytuacji`

#### Scenario: Mass signals
- **WHEN** the mock document `cdbf5306…` is analyzed without a judge
- **THEN** S3.3 is `pass`

### Requirement: S3.4 recommendation of specific instruments
S3.4 SHALL find a candidate when a recommending buy, sell or hold form (such as `kup`, `kupuj`, `kupno`, `sprzedaj`, `sprzedaż`, `trzymaj`, `rekomendujemy`, `rekomenduję`, `polecam kupić`, `co kupić`, `co sprzedać`) occurs within one sentence of an instrument noun from Art. 2-3 of the Act on Trading in Financial Instruments (`akcje`, `obligacje`, `ETF`, `CFD`, `opcje`, `kontrakty terminowe`, `futures`, `certyfikaty`, `jednostki funduszy`), quoting the sentence with the expression.

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

#### Scenario: S3.4 recommendation of specific instruments: further obligations
- **WHEN** this requirement is applied
- **THEN** First-person past forms (`kupiłam`, `sprzedałem`) and negated expressions (`nie udzielamy rekomendacji`, `nie polecamy kupna`) SHALL NOT be candidates.
- **AND** Plain crypto-assets (`bitcoin`, `BTC`, `ethereum`, `ETH`, `kryptowaluty`) SHALL NOT count as instruments; crypto CFDs, futures and options SHALL count, because the derivative noun matches whatever the underlying (Art. 2 lit. h/i).
- **AND** It carries an `llm:` block and is sent to the LLM whenever it applies.

### Requirement: S3.5 paid model
S3.5 SHALL be `fail` when the text has paid-model vocabulary (`abonament`, `subskrypcja`, `sygnały premium`, `VIP`, `płatna grupa`) or a monthly price in Polish or English (`<amount> zł/mies`, `PLN miesięcznie`, `<amount> PLN per month`, `<amount> EUR/month`, `$<amount> monthly`, a `subscription` or `monthly fee`), quoting it, and `pass` otherwise.

#### Scenario: Subscription
- **WHEN** the mock document `007bbcee…` is analyzed
- **THEN** S3.5 is `fail` with evidence from `Abonament 990 zł miesięcznie`

#### Scenario: Monthly price
- **WHEN** the mock document `cdbf5306…` is analyzed
- **THEN** S3.5 is `fail`

#### Scenario: Free content
- **WHEN** the mock document `72acbb3b…` is analyzed
- **THEN** S3.5 is `pass`

#### Scenario: English advisory offer
- **WHEN** an unregistered page says `We offer investment consulting and wealth advisory for Polish clients. Fee: 2000 PLN per month.`
- **THEN** an M3 finding is returned with S3.2 and S3.5 `fail`

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
S3.8 SHALL be `fail` when an S3.4 buy, sell or hold form occurs within one sentence of a plain crypto-asset word (`bitcoin`, `BTC`, `ethereum`, `ETH`, `kryptowaluty`, `altcoiny`) and no Art. 2-3 instrument noun is within that window, quoting the sentence, and `pass` otherwise. Its severity is low, its legal basis is art. 2 u.o.i.f. (Topic 3 annex), and its explanation SHALL say the assets are outside Art. 2 ("poza art. 2") because crypto-assets are not listed in the art. 2 catalogue.

#### Scenario: Crypto signal group
- **WHEN** an unregistered Polish post says `Kupuj bitcoina teraz, sprzedaj na szczycie. Grupa VIP 99 zł/mies.`
- **THEN** an M3 finding is returned with S3.8 `fail`, S3.4 `pass`, a score of at most 0.4, and a summary saying the assets are outside Art. 2

#### Scenario: Crypto derivative is not S3.8
- **WHEN** the text is `Kupuj CFD na bitcoina, zanim wystrzeli.`
- **THEN** S3.8 is `pass`

#### Scenario: S3.8 crypto-asset recommendations outside Art. 2: further obligations
- **WHEN** this requirement is applied
- **THEN** It counts as an advisory signal for routing but SHALL NOT lift the gate.

### Requirement: M3 score and hard gate
The M3 score SHALL be `σ(bias + Σ wᵢ·xᵢ)` with `bias` and weights from `m3_signals.yaml` (`x` as for M1), rounded to 3 decimals, ranking the Art. 76 elements: personalization together with a recommendation of instruments strongest, a recommendation of instruments alone strong, personalization alone weak, general education low. When S3.4 is neither `fail` nor `uncertain`, the score SHALL be at most 0.4 and the summary SHALL say it was capped. An `uncertain` S3.4 lifts the gate;

#### Scenario: Personalized paid recommendations
- **WHEN** the mock document `007bbcee…` is analyzed without a judge
- **THEN** the score is at least 0.7 (the M3 default threshold)

#### Scenario: Instrument recommendation alone is strong
- **WHEN** a page by an unregistered Polish entity has S3.4 `fail` (as the LLM will confirm it) and S3.2, S3.3 and S3.5 `pass`
- **THEN** the score is at least 0.7

#### Scenario: Personalization alone is weak
- **WHEN** a page has S3.3 `fail` and S3.4 `pass`
- **THEN** the score is at most 0.4 and the summary mentions the cap

#### Scenario: Both elements are strongest
- **WHEN** the same page has S3.3 and S3.4 both `fail`
- **THEN** its score is higher than with S3.4 `fail` alone

#### Scenario: Educational article is capped
- **WHEN** the M3 signals of the mock document `72acbb3b…` are scored
- **THEN** the score is at most 0.4 (the pipeline returns no finding for it, since it has no offer signal; requirement "Routing to modules" in `document-analysis`)

#### Scenario: Gate caps strong non-advisory signals
- **WHEN** a page has S3.1, S3.2, S3.5 and S3.6 `fail` and S3.3 and S3.4 `pass`
- **THEN** the score is exactly `min(σ(…), 0.4)` and the summary mentions the cap

#### Scenario: Mass signals without the LLM
- **WHEN** the mock document `cdbf5306…` is analyzed without a judge
- **THEN** the score is above 0.4 and below the score of the same results with S3.4 `fail`

#### Scenario: M3 score and hard gate: further obligations
- **WHEN** this requirement is applied
- **THEN** S3.3 alone SHALL NOT.

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
The M3 finding SHALL carry the challenge's M3 output: entity data in `advertiser` (`in_registry` false, `on_warning_list` null), the offer content in `content_excerpt` (a window of at most 500 characters around the first evidence found in the text) and the location in `url` and `platform`.

#### Scenario: Family office finding
- **WHEN** the mock document `007bbcee…` is analyzed
- **THEN** the finding has `firm` null, a title naming the advertiser, and passes `python contracts/validate.py finding`

#### Scenario: CLI over all mocks
- **WHEN** the CLI runs on `contracts/mocks/documents.json`
- **THEN** it exits 0 and its output, holding M1, M2 and M3 findings, passes `python contracts/validate.py finding`

#### Scenario: Candidate titles
- **WHEN** the mock document `cdbf5306…` is analyzed without the LLM (S3.4 `uncertain`)
- **THEN** the title contains `możliwe rekomendacje instrumentów finansowych`

#### Scenario: Unconfirmed personalisation
- **WHEN** an M3 finding has S3.4 `uncertain` or `fail` and S3.3 `pass`
- **THEN** the summary says that personalisation (art. 76) is unconfirmed

#### Scenario: Excerpt around the offer
- **WHEN** a long page has its buy recommendation only after 2000 characters of other text
- **THEN** `content_excerpt` has at most 500 characters and contains the start of the recommendation

#### Scenario: M3 finding assembly: further obligations
- **WHEN** this requirement is applied
- **THEN** It SHALL also have `module` M3, `firm` null, the M3 signal results, the raw `score`, a Polish title that names the advertiser and the deciding signal, prefixed "możliwe" while that signal is `uncertain`, and never states that the entity is outside the KNF register, a Polish summary listing present and uncertain signals and any cap or S3.8 note ("kryptoaktywa nie są wymienione w katalogu z art. 2 u.o.i.f.
- **AND** (załącznik do tematu 3)"), saying that personalisation (art. 76) is unconfirmed when S3.3 is `pass`, `status` new, and `model.llm` null in rules-only mode.
- **AND** It SHALL validate against `contracts/schemas/finding.schema.json` v1.

