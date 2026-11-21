## MODIFIED Requirements

### Requirement: Firm registry matching
Analytics SHALL load registered firms from the CSV at `REGISTRY_CSV`. It SHALL match a document to at most one firm by name or alias in the text, by the page domain, or by a fuzzy name match. The match SHALL have a confidence in 0-1. When the page host is a registered firm's domain, that firm SHALL be matched even if the text names another firm. When the registry file cannot be read, the error SHALL tell the operator to set `REGISTRY_CSV`.

#### Scenario: Name without legal form
- **WHEN** the text mentions `Alfa Inwestycje` and the registry holds `Alfa Inwestycje Dom Maklerski S.A.`
- **THEN** that firm is matched with confidence at least 0.9

#### Scenario: Domain match
- **WHEN** the document URL host is a subdomain of a firm's `website_domains` and its name is absent from the text
- **THEN** that firm is matched with confidence at least 0.8

#### Scenario: Own domain beats another firm's name
- **WHEN** a page on `alfa-inwestycje.example.com` mentions only `Bank Przykładowy`
- **THEN** the Alfa firm is matched by domain

#### Scenario: Earliest name wins a tie
- **WHEN** a page on no registered domain names two registry firms
- **THEN** the firm named first in the text is matched, even if its full legal name appears only later
- **AND** among equally confident name matches, the firm whose name or alias appears first in the text SHALL win, then the one with the longest quote

#### Scenario: No match
- **WHEN** no name, alias, domain or fuzzy candidate reaches the threshold
- **THEN** no firm is matched

#### Scenario: Registry file missing or malformed
- **WHEN** `REGISTRY_CSV` points to a missing file or a file without the required columns
- **THEN** startup fails with an error naming the file, never silently with an empty registry

#### Scenario: Hyphenated firm name
- **WHEN** the registry holds `Alfa-Beta Inwestycje S.A.` and the text says `Alfa-Beta Inwestycji`
- **THEN** that firm is matched by fuzzy match
- **AND** the fuzzy match SHALL tokenize the firm name the same way as the text, so punctuation inside a name (`Alfa-Beta`) does not lower the ratio

#### Scenario: Firm name without word tokens
- **WHEN** a registry firm's name has no word tokens
- **THEN** that name SHALL never fuzzy-match

#### Scenario: Registry path not set
- **WHEN** `REGISTRY_CSV` points to a missing file
- **THEN** the error names the file and `REGISTRY_CSV`

#### Scenario: Hostile page URL and lookalike names
- **WHEN** the page URL has a backslash, whitespace or control characters in its authority (`https://attacker.net\@alfa-inwestycje.example.com/`)
- **THEN** no firm SHALL be matched by the page domain, as for links and the publisher
- **AND** names and aliases SHALL be compared with the text after NFKC and removal of zero-width characters and soft hyphens, so `Ａｌｆａ Inwestycje` and `Alfa​ Inwestycje` match by name
- **AND** the quote SHALL still be cut from the original text through an offset map; Cyrillic and Greek lookalikes are not folded
- **AND** the fuzzy match SHALL need a ratio of at least 88: `Amega Kaital` (exactly 88 against `Omega Kapital`) matches, `Amga Kaital` does not

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
- **WHEN** a `firm_own` document matches no registry firm and has advisory vocabulary
- **THEN** exactly one M3 finding is returned and no M2 finding

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
- **AND** an M3-only document whose advisory signals S3.2, S3.3, S3.4, S3.5 and S3.8 are all `pass` SHALL produce no finding and log the reason `no_signals`
- **AND** a document SHALL produce at most one finding per module, and the reason `module_not_implemented` SHALL no longer be logged

### Requirement: Linear time on hostile text
Preprocessing and the rules-only checks SHALL run in time linear in the length of the text, because scraped text is untrusted. No regular expression on the analysis path may backtrack over a whitespace run, a digit run, a long word or a growing sentence prefix, and no rule may compare every sentence with every other. Sentence boundaries and their offsets into the original text SHALL be the same as before for ordinary text.

#### Scenario: Long whitespace run
- **WHEN** the text is `"."` followed by 50 000 spaces, or `". "` + 40 000 spaces + `abc`
- **THEN** sentence splitting finishes in under a second

#### Scenario: Abbreviation chain
- **WHEN** the text repeats `S.A. Ab ` or `ok. 1 ` thousands of times
- **THEN** sentence splitting finishes in under a second, and `S.A.` still never ends a sentence

#### Scenario: Long digit run
- **WHEN** the text contains 50 000 digits with no `%`
- **THEN** the full M2 analysis finishes in under three seconds, and `Zarabiaj 12,5 % rocznie` is still an R3 claim

#### Scenario: Footnote marker followed by spaces
- **WHEN** a sentence ends and the next starts with `*` or `(*)` followed by up to three spaces and a capital
- **THEN** a new sentence starts at the marker

#### Scenario: Many claim and warning sentences
- **WHEN** the text repeats `Zysk 5%. Ryzyko straty.` 8 000 times, or a fee stem such as `prowizj` 8 000 times in one word
- **THEN** the full M2 analysis finishes in under three seconds, and R3's ±2 sentence window gives the same result as before

#### Scenario: Megabyte of hostile text
- **WHEN** 1 MB of `"1,"`, of zero-width characters or of one-letter words is analyzed
- **THEN** routing and the M1/M3 rules SHALL see at most the first 200 000 characters, with every evidence quote a substring of the original text
- **AND** the whole analysis costs about no more than for the first 200 000 characters, while M2 rules still see the whole text
