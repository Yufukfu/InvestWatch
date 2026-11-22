## MODIFIED Requirements

### Requirement: Routing to modules
Analytics SHALL route by publisher identity and registry result, not by `source_kind` alone (design decisions 1-2). The publisher is a registry firm when the author's `profile_url` host or a non-social page host is one of the firm's `website_domains` (equal or subdomain). A handle alone SHALL NOT make the publisher a registered firm.

#### Scenario: Handle like a firm's name on another platform
- **WHEN** a `third_party` TikTok post by `@alfainwestycje` (no profile or page on the firm's domain) names Alfa Inwestycje
- **THEN** an M1 finding is returned and no M2 finding, with S1.6 `uncertain`

#### Scenario: Firm's own page
- **WHEN** a `firm_own` document on a registered firm's domain is analyzed
- **THEN** exactly one M2 finding is returned

#### Scenario: Own material of a foreign firm without a branch
- **WHEN** a `firm_own` page on the domain of a `foreign_no_branch` firm, or a post by that firm's own account, is analyzed
- **THEN** no finding is returned and the log names the reason `out_of_scope_m2_foreign_no_branch`

#### Scenario: Third-party ad of a foreign firm without a branch
- **WHEN** a Polish third-party post advertises a `foreign_no_branch` firm
- **THEN** exactly one M1 finding is returned

#### Scenario: Own page of a foreign branch
- **WHEN** a `firm_own` page on the domain of a `foreign_branch` firm is analyzed
- **THEN** exactly one M2 finding is returned

#### Scenario: Firm's own page without a registry match
- **WHEN** a `firm_own` document matches no registry firm and has an offer signal (a recommendation of instruments, personalization, a paid model or crypto-asset calls)
- **THEN** exactly one M3 finding is returned and no M2 finding

#### Scenario: Service vocabulary alone is no offer
- **WHEN** an `unknown` page by an unregistered entity on a Polish host has only service vocabulary (`family office`, `doradztwo inwestycyjne`), so S3.1, S3.2 and S3.6 are `fail` and S3.3, S3.4, S3.5 and S3.8 are `pass`
- **THEN** no finding is returned and the log names the reason `no_signals`

#### Scenario: Educational family-office explainer
- **WHEN** the mock document `72acbb3b…` (family-office explainer that says it gives no recommendations) is analyzed
- **THEN** no finding is returned and the log names the reason `no_signals`

#### Scenario: Supervisor's public-warnings page
- **WHEN** a `third_party` page on `www.knf.gov.pl` lists EuroTrade (a registry firm) and an unregistered entity offering investment advice
- **THEN** no finding is returned and the log names the reason `official_source`

#### Scenario: Government subdomain and configured list
- **WHEN** the page host is `uknf.gov.pl` or any subdomain of `gov.pl`, or `OFFICIAL_SOURCE_DOMAINS` names the host or a parent domain of it
- **THEN** no module runs for the document, whatever its `source_kind` and text

#### Scenario: Look-alike host is not official
- **WHEN** the page host is `knf.gov.pl.example.com` or `fakeknf-gov.pl`
- **THEN** the document is routed as usual

#### Scenario: Unmatched own page without advisory signals
- **WHEN** a `firm_own` document matches no registry firm and has no advisory signal
- **THEN** no finding is returned and the log names the reason `no_signals`

#### Scenario: Firm's own social account
- **WHEN** a `third_party` Instagram post names Alfa Inwestycje and its author has handle `@alfainwestycje`
- **THEN** exactly one M2 finding for the Alfa firm is returned and no M1 finding

#### Scenario: Third-party post about a registered firm
- **WHEN** the mock document `3c41441c…` (`third_party`, names EuroTrade) is analyzed
- **THEN** exactly one finding is returned, with `module` M1

#### Scenario: Foreign firm's ad not aimed at Poland
- **WHEN** an English third-party post on a `.com` host names a `foreign_no_branch` firm and has no PLN amount, `+48` number or Polish text
- **THEN** no finding is returned and the log names the reason `not_targeting_poland`

#### Scenario: Foreign branch advertised in English
- **WHEN** the same English post names EuroTrade (`foreign_branch`)
- **THEN** exactly one M1 finding is returned

#### Scenario: Polish brokerage house advertised in English
- **WHEN** an English third-party post on a `.com` host names Alfa Inwestycje (`brokerage_house`) and has no Polish marker
- **THEN** exactly one M1 finding is returned, with S1.7 `pass`

#### Scenario: Unknown-source page of an unregistered entity
- **WHEN** the mock document `007bbcee…` (`unknown`, no registry firm) is analyzed
- **THEN** exactly one finding is returned, with `module` M3

#### Scenario: Unmatched post without advisory signals
- **WHEN** the mock document `8721cb75…` (`third_party`, educational, no registry firm) is analyzed
- **THEN** no finding is returned and the log names the reason `no_signals`

#### Scenario: Empty text is still skipped before routing
- **WHEN** a `third_party` document has whitespace-only `text`
- **THEN** no finding is returned and the log names the reason `empty_text`

#### Scenario: Routing to modules: which module runs
- **WHEN** a document with text is routed
- **THEN** M2 SHALL run for the publisher firm when the publisher is a registry firm, whatever the `source_kind`, and for a `firm_own` document that the registry matches by text or page host
- **AND** no module SHALL run for the own material of a foreign firm without a Polish branch (`foreign_no_branch`), which SHALL produce no finding and log the reason `out_of_scope_m2_foreign_no_branch`: M2 covers firms registered in Poland, including Polish branches of foreign firms, and such a firm is authorized, so it is not M3 either
- **AND** M1 SHALL run for a `third_party` or `unknown` document whose publisher is not a registry firm and that mentions a registry firm by text or link host
- **AND** an M1 candidate whose firm is `foreign_no_branch` and that does not target Poland (S1.7 `pass`) SHALL produce no finding and log the reason `not_targeting_poland`, while a firm registered in Poland (`brokerage_house`, `brokerage_bank`, `foreign_branch`) stays in M1 scope whatever the language
- **AND** M3 SHALL run for a document whose publisher is not a registry firm and that the registry does not match, including an unmatched `firm_own` document, which SHALL never go to M2
- **AND** M3 SHALL also run alongside M1 when the M1 document carries an S3.3 or S3.4 candidate attributed to the publisher (requirement "M3 alongside M1" in `m3-unauthorized-advice-signals`)
- **AND** an M3-only document with no offer signal (S3.3, S3.4, S3.5 and S3.8 all neither `fail` nor `uncertain`) SHALL produce no finding and log the reason `no_signals`; service vocabulary (S3.2), an entity outside the registry (S3.1) and targeting Poland (S3.6) only raise the score of an offer and are no offer on their own
- **AND** no module SHALL run for a document whose page host is a supervisor or official-register domain (`knf.gov.pl`, `uknf.gov.pl`, `gov.pl` and its subdomains by default, replaced by `OFFICIAL_SOURCE_DOMAINS` when set): such a page is never an M1 advertiser, an M2 firm or an M3 publisher, and SHALL produce no finding and log the reason `official_source`
- **AND** a document SHALL produce at most one finding per module, and the reason `module_not_implemented` SHALL no longer be logged

## ADDED Requirements

### Requirement: Preprocessing normalizes once
Preprocessing SHALL apply Unicode NFKC and whitespace collapsing to a document's text once and derive `normalized` and the language guess from that one result, so the normalization cost is paid once per document and not once per derived field. The result SHALL be identical to deriving each field separately: the same normalized text, language, and sentences with the same offsets into the original text.

#### Scenario: Same result as before
- **WHEN** a mock document text, or a seeded random text with compatibility characters (`ﬁ`, fullwidth letters, NBSP), CRLF and mixed whitespace, is preprocessed
- **THEN** `normalized`, `lang` and every sentence's text, `start` and `end` equal those computed field by field

#### Scenario: One NFKC pass
- **WHEN** a text is preprocessed
- **THEN** `unicodedata.normalize` runs exactly once on it

#### Scenario: Large ligature text grows linearly
- **WHEN** the text is 100 000 and then 400 000 copies of `ﬁ`
- **THEN** the time ratio of the two runs stays within linear growth (4x plus a margin, far below the 16x of quadratic growth), measured as a ratio and never as wall-clock seconds
