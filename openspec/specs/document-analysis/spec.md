# document-analysis Specification

## Purpose
Turn one scraped document into explainable, contract-valid findings, without any infrastructure, so the same pure function can sit behind the Redis worker.

## Requirements

### Requirement: Lenient input, strict output
Analytics SHALL accept any document that has the required `ScrapedDocument` v1 fields (`.docs/integration-plan.md` §3) and ignore unknown fields. Every `Finding` it emits SHALL validate against `contracts/schemas/finding.schema.json` v1.

#### Scenario: Contract mocks are accepted
- **WHEN** each document in `contracts/mocks/documents.json` is parsed
- **THEN** parsing succeeds for all of them

#### Scenario: Unknown field is ignored
- **WHEN** a document carries an extra top-level field not in the v1 schema
- **THEN** it is parsed and the extra field is dropped

#### Scenario: Missing required field
- **WHEN** a document has no `text` or a malformed `fetched_at`
- **THEN** parsing raises a validation error naming the field and no finding is produced

#### Scenario: Output is contract-valid
- **WHEN** the pipeline produces findings for the mock documents
- **THEN** `python contracts/validate.py finding <output>` exits 0

### Requirement: Preprocessing
Analytics SHALL normalize text (Unicode NFKC, collapsed whitespace) and split it into sentences. It SHALL compute `content_hash` as sha256 of the normalized text and guess the language as `pl` or `en`. Evidence quotes SHALL still be exact substrings of the original `text`. Legal forms, titles and `<year> r.` SHALL NOT end a sentence; abbreviations that are also ordinary words (`ok.`, `tel.`, `art.` and similar) SHALL end one unless a digit follows, directly or after an opening bracket or quote.

#### Scenario: Equivalent texts hash the same
- **WHEN** two texts differ only in whitespace runs or Unicode composition
- **THEN** their content hashes are equal

#### Scenario: Sentence split keeps legal forms
- **WHEN** the text is `Reklama. Bank Przykładowy S.A. – Biuro Maklerskie. Otwórz IKE.`
- **THEN** it splits into three sentences and `S.A.` does not end a sentence

#### Scenario: Ordinary word that is also an abbreviation
- **WHEN** the text is `Wszystko jest ok. Zysk 15% rocznie.`
- **THEN** it splits into two sentences, while `Zysk wynosi ok. 15% rocznie.` stays one

#### Scenario: Language guess
- **WHEN** the text is Polish marketing copy, and separately an English risk warning
- **THEN** the guesses are `pl` and `en`

#### Scenario: Empty text
- **WHEN** `text` is empty or whitespace only
- **THEN** the pipeline returns no findings and logs the reason `empty_text`

### Requirement: Firm registry matching
Analytics SHALL load registered firms from the CSV at `REGISTRY_CSV`, by default the real KNF register `registry/knf.csv`. It SHALL match a document to at most one firm by name or alias in the text, by the page domain, or by a fuzzy name match. The match SHALL have a confidence in 0-1. When the page host is a registered firm's domain, that firm SHALL be matched even if the text names another firm. When the registry file cannot be read, the error SHALL tell the operator to set `REGISTRY_CSV`.

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

#### Scenario: Foreign legal form stripped
- **WHEN** the registry holds `Admiral Markets AS` and the text mentions `Admiral Markets`
- **THEN** that firm is matched by name with confidence at least 0.9
- **AND** the core name SHALL drop the Polish and EU legal forms found on the KNF lists (`S.A.`, `Sp. z o.o.`, `Dom Maklerski`, `GmbH`, `AG`, `B.V.`, `a.s.`, `Ltd`, `Limited`, `SAS`, `AS`, `UAB`), short ones only at the end of the name

#### Scenario: Short word in lower case never matches
- **WHEN** the registry holds `EXT Ltd` and `Nova AG`, and the text says `next step` and `bossa nova`
- **THEN** neither firm is matched
- **AND** a short word (a core or alias of one word under 8 letters) SHALL never fuzzy-match

#### Scenario: Short core matched by its full name
- **WHEN** the registry holds `Nova AG` and the text says `Nova AG`
- **THEN** that firm is matched by name

#### Scenario: Short brand matched as a capitalized word
- **WHEN** the registry holds `XTB S.A.` and the text says `Otwórz konto w XTB`
- **THEN** that firm is matched by name with evidence `XTB`
- **AND** a short word SHALL match only capitalized, lower-first where the registry writes it so (`mBank`), or in brand casing with an inner capital (`eToro` for `Etoro`)

#### Scenario: Acronym only in capitals
- **WHEN** the registry holds `EVO Ltd` with alias `EVO` and the text says `Nowa wersja Evo`
- **THEN** no firm is matched, while `Konto w EVO` matches it

#### Scenario: Shared core goes to the Polish firm
- **WHEN** the registry holds the brokerage house `XTB S.A.` and the foreign firm without a branch `XTB Ltd`, and the text says `XTB`
- **THEN** `XTB S.A.` is matched
- **AND** a form shared by firms of the same highest type SHALL match neither of them, while `find_name` for an already chosen firm searches all its forms

#### Scenario: Multi-word core still fuzzy-matches
- **WHEN** the registry holds `Wise Assets Europe AS` and the text says `Wise Asets Europe`
- **THEN** that firm is matched by fuzzy match
- **AND** the fuzzy match SHALL read only the first 20,000 characters of the folded text, while exact names are found in the whole scan prefix

#### Scenario: Firm without domains
- **WHEN** a firm has an empty `website_domains` and the page host is any host
- **THEN** that firm is never matched by domain, only by name, alias or fuzzy match

#### Scenario: Real-size registry within budget
- **WHEN** a registry of 1,000 firms matches a 20,000-character text
- **THEN** the match returns in under 1 second

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

### Requirement: M2 finding assembly
The M2 finding SHALL list only the results of implemented rules. It SHALL carry the raw `score` (never `risk_level`), the matched firm (or `null`), a Polish title and summary, `status: new`, the `url` and `platform` copied from the document, `content_excerpt` of at most 500 characters, and `model.llm`. The score SHALL be `Σ(weight·fail) / Σ(weight·applicable)` with weights high 3, medium 2, low 1, where `uncertain` counts as half a fail and `not_applicable` is excluded.

#### Scenario: Violating landing page
- **WHEN** the mock document `m2-alfa-landing` (id `a3c88321-…`) is analyzed rules-only
- **THEN** the finding has R1 `pass`, R2 `fail`, R3 `fail`, R4 `fail`, R6 `fail`, R18 `fail` and a score above 0.5

#### Scenario: Compliant material
- **WHEN** the mock document `m2-bank-ok` (id `5030107e-…`) is analyzed
- **THEN** no rule result is `fail`, R4 and R6 are `not_applicable`, and the score is 0

#### Scenario: Builder without a firm match
- **WHEN** the M2 builder is called directly with a context that has no firm match
- **THEN** the finding has `firm: null` and R1 `fail`
- **AND** the pipeline never produces an M2 finding with `firm: null`, because routing sends only registered firms to M2

#### Scenario: Firm matched by domain only
- **WHEN** a `firm_own` page on the Alfa domain does not name the firm in its text
- **THEN** the M2 finding has the Alfa firm and R1 `fail`

#### Scenario: Rule that does not apply
- **WHEN** R3 is `not_applicable`
- **THEN** the summary does not list R3 among the checked rules and says it does not apply
- **AND** the summary SHALL name as checked only the rules that applied, and name `not_applicable` rules separately
- **AND** when no rule applies (every rule is `not_applicable`), the score is 0

#### Scenario: LLM used
- **WHEN** `m2-alfa-landing` is analyzed with a stub judge whose valid R17 verdict is merged and `LLM_MODEL=gemma3:4b`
- **THEN** `model.llm` is `gemma3:4b` and the summary names the model and R17
- **AND** `model.llm` SHALL be the configured `LLM_MODEL` only when at least one rule result of the finding has `method` `llm` or `hybrid`

#### Scenario: LLM configured but not used
- **WHEN** the judge is configured and the endpoint is down
- **THEN** `model.llm` is `null` and the summary says the check ran rules-only
- **AND** `model.llm` SHALL be `null` whenever the LLM is disabled, nothing was deferred, or the LLM failed

### Requirement: Command-line batch
The CLI SHALL validate each document of a batch on its own. An invalid document SHALL be logged with its index and the error locations and types, without input values, and skipped. The CLI SHALL exit 2 without writing to stdout when the input has documents and none is valid. If analyzing a valid document raises, the CLI SHALL log the document id and the exception type (no input values), skip that document, still write the findings of the others, and exit 1.

#### Scenario: One bad document in a batch
- **WHEN** a list holds one valid document and one without `text`
- **THEN** the CLI exits 0 with the finding of the valid document and logs the skipped index

#### Scenario: Nothing valid
- **WHEN** every document in the list is invalid
- **THEN** the CLI exits 2 and writes nothing to stdout

#### Scenario: Unreadable input or bad configuration
- **WHEN** the input cannot be read, or the configuration is bad
- **THEN** the CLI SHALL exit 2 without writing to stdout
- **AND** a catalogue whose root is not a mapping SHALL be bad configuration (exit 2)

#### Scenario: Log carries no document content
- **WHEN** an invalid document is logged
- **THEN** the log line does not contain the document's field values

#### Scenario: Analysis fails for one document
- **WHEN** a batch holds two valid documents and analyzing the first raises an unexpected error
- **THEN** the CLI writes the second document's finding, logs the first document's id and the exception type, and exits 1

### Requirement: Registry match on link hosts for third-party content
For `third_party` and `unknown` documents, when neither the text nor the page host matches a registry firm, analytics SHALL compare the host of each `links[].href` with the firms' `website_domains` (equal or subdomain), and a hit SHALL match that firm with confidence 0.9, quoting the href. A malformed or non-http(s) href SHALL be skipped without error. `firm_own` documents SHALL keep the text-and-page-host match only.

#### Scenario: Referral link to a firm domain
- **WHEN** a `third_party` post names no firm and links to `https://eurotrade-markets.example.com/pl/register?ref=X`
- **THEN** the EuroTrade firm is matched by link host and the document is routed to M1

#### Scenario: Malformed link
- **WHEN** a `third_party` post has a link with href `not a url`, advisory vocabulary and no other match
- **THEN** analysis succeeds, no firm is matched, and the document is routed to M3

#### Scenario: Social platform page host
- **WHEN** a post on `https://www.instagram.com/p/…` names no firm and has no links
- **THEN** no firm is matched

### Requirement: Signal catalogue
Analytics SHALL load the M1 and M3 signal catalogues from `rules/m1_signals.yaml` and `rules/m3_signals.yaml` with the shared rule-catalogue loader. Each signal catalogue SHALL have a numeric `bias`, and each entry an id (`S1.<n>` in the M1 file, `S3.<n>` in the M3 file), a Polish name, a severity, a numeric `weight`, an `implemented` flag and its parameters; S1.4, S1.5, S3.3 and S3.4 SHALL also carry an `llm:` block in the format of `analytics-llm-p0`.

#### Scenario: Catalogues load
- **WHEN** both catalogues are loaded
- **THEN** M1 holds S1.1-S1.7 all implemented, and M3 holds S3.1-S3.8 with exactly S3.7 not implemented

#### Scenario: Malformed signal catalogue
- **WHEN** an entry has id `S3.2` in the M1 file, or a weight `high`, or the root has no `bias`
- **THEN** loading fails with an error naming the file and the entry

#### Scenario: Signal id in the M2 catalogue
- **WHEN** `m2_rules.yaml` holds an entry with id `S1.1`
- **THEN** loading fails with an error naming the entry

#### Scenario: Bad signal parameter
- **WHEN** a pattern list contains an invalid regex or an unknown parameter key
- **THEN** loading fails at startup, not on the first document

#### Scenario: Signal catalogue: further obligations
- **WHEN** this requirement is applied
- **THEN** Loading SHALL fail with an error naming the file and the entry on a duplicate or wrongly prefixed id, an unknown severity, a missing or non-numeric weight or bias, an unknown parameter key, or a regex that does not compile.
- **AND** The M2 catalogue SHALL keep accepting only `R…` ids.
- **AND** Only implemented signals SHALL run.

### Requirement: Signal evidence sources
Every signal result with non-null `evidence` SHALL quote a verbatim substring of one of the fields its rule declares as evidence fields: `text` for every rule, and for M1/M3 signals that quote metadata also `author.name`, `author.handle`, each `links[].href` and `url`. The explanation SHALL say where the quote was found when it is not `text`. A result whose quote is in none of its declared fields SHALL become `uncertain` with null evidence.

#### Scenario: Evidence check on the mocks
- **WHEN** M1/M3 run on the six M1/M3 mock documents
- **THEN** each non-null evidence is found verbatim in the field its result names

#### Scenario: Quote from a link
- **WHEN** S1.2 fires on the href `https://eurotrade-markets.example.com/pl/register?ref=JAN500`
- **THEN** its evidence is a substring of that href and the explanation says it is in a link

#### Scenario: Unverifiable quote
- **WHEN** a signal returns a quote that is in none of its declared fields
- **THEN** the result is `uncertain` and its evidence is null

#### Scenario: M2 rule quoting metadata
- **WHEN** an M2 rule returns the author handle as evidence and the handle is not in `text`
- **THEN** the result is `uncertain` and its evidence is null

#### Scenario: Signal evidence sources: further obligations
- **WHEN** this requirement is applied
- **THEN** M2 rules SHALL keep `text` as their only evidence field.
- **AND** Every result SHALL carry the catalogue's name and severity, and `method` `rule`, `llm` or `hybrid`.

### Requirement: Advertiser on M1 and M3 findings
M1 and M3 findings SHALL carry `advertiser` in the `Finding` v1 shape (`.docs/integration-plan.md` §4). `name` SHALL be `author.name`, else `author.handle`, else the page host unless it is a social platform host, in which case `name` SHALL be null. `handle` and `profile_url` SHALL come from `author`; a `profile_url` that is not an absolute http(s) URL SHALL become null without failing the finding.

#### Scenario: Finfluencer advertiser
- **WHEN** the mock document `3c41441c…` is analyzed
- **THEN** `advertiser` is name `Jan Inwestor`, handle `@inwestor_jan`, profile URL `https://www.instagram.com/inwestor_jan/`, `in_registry` false

#### Scenario: Web page without an author
- **WHEN** the mock document `007bbcee…` is analyzed
- **THEN** `advertiser.name` is the page host, `website` is `https://zlotykapital-fo.example.com/`, `in_registry` false and `on_warning_list` null

#### Scenario: Malformed author profile URL
- **WHEN** a `third_party` document has `author.profile_url` `javascript:alert(1)`
- **THEN** the finding is produced with `advertiser.profile_url` null

#### Scenario: Very long author name
- **WHEN** `author.name` is 5000 characters long
- **THEN** `advertiser.name` has at most 200 characters

#### Scenario: Social post without an author
- **WHEN** an Instagram post about a registered firm has no author
- **THEN** `advertiser.name` and `advertiser.website` are null

#### Scenario: Advertiser on M1 and M3 findings: further obligations
- **WHEN** this requirement is applied
- **THEN** `website` SHALL be the page origin when the document has no author and the page host is not a social platform host, else null.
- **AND** Strings SHALL be trimmed and cut to 200 characters.
- **AND** `in_registry` SHALL be the publisher identity of the routing requirement, so it is false on every M1 and M3 finding.
- **AND** `on_warning_list` SHALL be null while S3.7 is not implemented.
- **AND** M2 findings SHALL keep `advertiser` null.

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

### Requirement: Investment topic gate
After preprocessing and before any module runs, analytics SHALL decide whether a document is investment-related (`.docs/analytics-plan.md` §2 step 2). Its core signal is dictionary hits: the terms of `gate_terms.yaml` (stems or phrases on word boundaries) matched against the normalized text, lowercased and with diacritics stripped. A registry firm match SHALL count as a hit. The gate SHALL drop a document only when it has no hit.

#### Scenario: Investment post passes on the dictionary
- **WHEN** a `third_party` post says `Zainwestuj w CFD na forex, zyski 20% miesięcznie`
- **THEN** the gate passes it with `dict_hits` at least 3, whether or not an embedder is configured

#### Scenario: Social post without diacritics
- **WHEN** a post says `gielda i kryptowaluty, moje zyski z inwestycji`
- **THEN** the gate passes it on the dictionary

#### Scenario: Inflected forms
- **WHEN** posts contain `zysków`, `zyskow` or `zainwestuj` and no other term
- **THEN** each passes on the dictionary

#### Scenario: Term inside another word
- **WHEN** a post contains `ketfon` but no investment term
- **THEN** `ETF` does not match and the post is dropped

#### Scenario: Embedder down, investment vocabulary
- **WHEN** the embedder is unavailable and a post mentions `obligacje skarbowe`
- **THEN** the gate passes it, and its findings have `model.embedder = null`

#### Scenario: Gate terms file invalid
- **WHEN** `gate_terms.yaml` has an empty term list
- **THEN** loading fails at start-up with an error naming the file and the key

### Requirement: Which documents are gated
Documents with `source_kind` `firm_own` SHALL bypass the gate, because M2 covers only material that firms publish themselves. `third_party` and `unknown` documents SHALL be gated, and those that pass SHALL flow to routing (M1/M3) unchanged. `GATE_ENABLED=false` SHALL let every document through.

#### Scenario: Firm page bypasses the gate
- **WHEN** a `firm_own` document has no dictionary hit
- **THEN** it is not dropped and is routed to M2 as before

#### Scenario: Unknown source kind is gated
- **WHEN** an `unknown` document about a football match has no dictionary hit
- **THEN** it is dropped with `off_topic`, while an `unknown` document mentioning `sygnały forex` passes and is routed

#### Scenario: Gate disabled
- **WHEN** `GATE_ENABLED=false` and an off-topic post is analyzed
- **THEN** the gate drops nothing

### Requirement: Dropped documents are logged
A document dropped by the gate SHALL produce no finding. It SHALL log `document skipped` with reason `off_topic` and the figures `dict_hits`, `similarity` (always null until a similarity rescue exists) and `embedder` (the model, or null), without document text. Its `documents` row SHALL stay untouched, so it can be re-analyzed.

#### Scenario: Off-topic post dropped with a reason
- **WHEN** a `third_party` post about a recipe has no dictionary hit
- **THEN** no finding is returned, and the log line has reason `off_topic`, `dict_hits` 0 and `similarity` null

#### Scenario: No text in the log
- **WHEN** a post containing `Przepis na sernik babci` is dropped
- **THEN** no log line contains that text

### Requirement: Gate counters
The gate SHALL increment `passed`, `dropped` or `bypassed` in the Redis hash `iw:stats:gate` for each decision when a Redis client is available. A Redis error on the counter SHALL be logged and never raised.

#### Scenario: Drop counted
- **WHEN** an off-topic post is dropped in the worker
- **THEN** `iw:stats:gate` `dropped` is incremented by 1

#### Scenario: Counter on a Redis outage
- **WHEN** the Redis client raises on `HINCRBY iw:stats:gate`
- **THEN** the gate decision and the analysis are unchanged

### Requirement: Near-duplicate detection
Analytics SHALL detect near-duplicates with MinHash (`NEARDUP_NUM_PERM` permutations, deterministic in every process) over word 5-shingles of the normalized, lowercased text, cut to `NEARDUP_MAX_CHARS`, and an LSH index of `NEARDUP_BANDS` bands in Redis. A band candidate SHALL count only if its estimated Jaccard similarity is at least `NEARDUP_THRESHOLD`. A document SHALL never match its own id. Texts with fewer than 5 words SHALL skip detection.

#### Scenario: Repost with a changed handle
- **WHEN** two `third_party` posts share the same 300-word text except for the author handle and one emoji
- **THEN** the second post is detected as a near-duplicate of the first, and both are analyzed

#### Scenario: Different texts
- **WHEN** two posts about different offers share fewer than half of their shingles
- **THEN** neither is recorded as a near-duplicate of the other

#### Scenario: Redelivery is not its own duplicate
- **WHEN** the same document id is analyzed twice
- **THEN** its group has one member and the summary has no near-dup sentence

#### Scenario: Too short
- **WHEN** the text has four words
- **THEN** no MinHash is computed and no Redis key is written for it

#### Scenario: Long text is bounded
- **WHEN** the normalized text is 2 MB long
- **THEN** only the first `NEARDUP_MAX_CHARS` characters are shingled, and detection finishes in under one second

#### Scenario: Works without embeddings
- **WHEN** `EMBED_BASE_URL` is unset and a repost is analyzed
- **THEN** it is still detected as a near-duplicate of its original

### Requirement: Near-duplicate groups in Redis
A near-duplicate SHALL still be analyzed and get its own findings. Its group SHALL be recorded in Redis with TTL `NEARDUP_TTL_S`:
- `iw:neardup:v1:doc:{document_id}` maps it to the group id (the earliest member's `document_id`);
- `iw:neardup:v1:group:{group_id}` holds the member ids;
- `iw:neardup:v1:meta:{document_id}` holds the signature and `url`.

A Redis error SHALL skip detection, logged as `neardup_unavailable`, never raised. Without an index (CLI), detection is off.

#### Scenario: Changed page version
- **WHEN** a firm page is re-scraped with one sentence changed (10 of 400 words), giving a new `document_id`
- **THEN** both documents are in one group and each has its own M2 finding (the `Finding` contract is unchanged)

#### Scenario: Group keys
- **WHEN** a repost joins the group of its original
- **THEN** `iw:neardup:v1:doc:{repost_id}` holds the original's id, the group set has both ids, and every key has a TTL

#### Scenario: Best group wins
- **WHEN** a document matches members of two different groups
- **THEN** it joins the group with the higher Jaccard similarity

#### Scenario: Index down
- **WHEN** the Redis client raises a connection error during the near-dup lookup
- **THEN** the document is analyzed, its summary has no near-dup sentence, and the log reason is `neardup_unavailable`

### Requirement: Near-duplicate summary sentence
Each finding of a document that is not its group's original SHALL carry one Polish sentence in its `summary` naming the original's URL and the number of near-identical analyzed materials. The finding's own `url` SHALL stay the near-duplicate's URL. The group SHALL be logged (`neardup`, with group id, best similarity and member count) without text. Exact duplicates by `content_hash` within one source remain the scraper's concern (document-ingest).

#### Scenario: Repost names the original
- **WHEN** a repost joins the group of an original at `https://example.com/a`
- **THEN** the repost's findings keep the repost's `url`, and their summary has one sentence naming `https://example.com/a`

#### Scenario: Original has no sentence
- **WHEN** the group's original is analyzed again after copies joined
- **THEN** its findings' summary has no near-dup sentence

### Requirement: Embedder recorded on findings
Every finding SHALL set `model.embedder` to `EMBED_MODEL` when a validated document vector, from the endpoint or the cache, was obtained for that document. It SHALL be `null` otherwise: embeddings disabled, unavailable, malformed, or breaker-open. Findings SHALL stay valid against `contracts/schemas/finding.schema.json` v1, and no contract field SHALL be added.

#### Scenario: Embedder used
- **WHEN** a passing post is analyzed with a stub embedder returning a valid vector and `EMBED_MODEL=bge-m3`
- **THEN** its findings have `model.embedder` `bge-m3` and validate with `contracts/validate.py finding`

#### Scenario: Cached vector counts as used
- **WHEN** the vector comes from the Redis cache and no request is made
- **THEN** `model.embedder` is `bge-m3`

#### Scenario: Embedder failed
- **WHEN** the stub returns a wrong-size vector
- **THEN** the findings have `model.embedder = null`
