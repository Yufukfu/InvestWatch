## MODIFIED Requirements

### Requirement: S3.1 entity not in the registry
S3.1 SHALL be `fail` for every M3 finding (routing sends a publisher that is a registry firm to M2, so the entity behind an M3 offer is never in the registry), quoting `author.handle`, else `author.name`, else the page host from `url`. Its explanation SHALL say the entity was not found in the loaded firm registry ("nie znaleziono w załadowanym rejestrze firm"), never that it is outside the KNF register as a fact, and SHALL add "(dane demonstracyjne)" while the loaded registry is the bundled demonstration data. The registry loader SHALL mark a registry as demonstration data when none of its firms has a `source_url` (the real KNF loader sets one per firm). S3.1 SHALL have no legal basis.

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

### Requirement: S3.8 crypto-asset recommendations outside Art. 2
S3.8 SHALL be `fail` when an S3.4 buy, sell or hold form occurs within one sentence of a plain crypto-asset word (`bitcoin`, `BTC`, `ethereum`, `ETH`, `kryptowaluty`, `altcoiny`) and no Art. 2-3 instrument noun is within that window, quoting the sentence, and `pass` otherwise. Its severity is low, its legal basis is art. 2 u.o.i.f. (Topic 3 annex), and its explanation SHALL say the assets are outside Art. 2 ("poza art. 2") because crypto-assets are not listed in the art. 2 catalogue. It counts as an advisory signal for routing but SHALL NOT lift the gate.

#### Scenario: Crypto signal group
- **WHEN** an unregistered Polish post says `Kupuj bitcoina teraz, sprzedaj na szczycie. Grupa VIP 99 zł/mies.`
- **THEN** an M3 finding is returned with S3.8 `fail`, S3.4 `pass`, a score of at most 0.4, and a summary saying the assets are outside Art. 2

#### Scenario: Crypto derivative is not S3.8
- **WHEN** the text is `Kupuj CFD na bitcoina, zanim wystrzeli.`
- **THEN** S3.8 is `pass`

### Requirement: M3 finding assembly
The M3 finding SHALL carry the challenge's M3 output: entity data in `advertiser` (`in_registry` false, `on_warning_list` null), the offer content in `content_excerpt` (a window of at most 500 characters around the first evidence found in the text) and the location in `url` and `platform`. It SHALL also have `module` M3, `firm` null, the M3 signal results, the raw `score`, a Polish title that names the advertiser and the deciding signal, prefixed "możliwe" while that signal is `uncertain`, and never states that the entity is outside the KNF register, a Polish summary listing present and uncertain signals and any cap or S3.8 note ("kryptoaktywa nie są wymienione w katalogu z art. 2 u.o.i.f. (załącznik do tematu 3)"), saying that personalisation (art. 76) is unconfirmed when S3.3 is `pass`, `status` new, and `model.llm` null in rules-only mode. It SHALL validate against `contracts/schemas/finding.schema.json` v1.

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
