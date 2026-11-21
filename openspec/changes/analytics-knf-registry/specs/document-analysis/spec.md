## MODIFIED Requirements

### Requirement: Firm registry matching
Analytics SHALL load registered firms from the CSV at `REGISTRY_CSV`, which defaults to the real KNF register `registry/knf.csv`; the fictional `registry/seed.csv` is the test fixture. It SHALL match a document to at most one firm by name or alias in the text, by the page domain, or by a fuzzy name match. The match SHALL have a confidence in 0-1. When the page host is a registered firm's domain, that firm SHALL be matched even if the text names another firm. Among equally confident name matches, the firm whose name or alias appears first in the text SHALL win, then the one with the longest quote. The core name SHALL drop the Polish and EU legal forms found on the KNF lists (for example `S.A.`, `Sp. z o.o.`, `Dom Maklerski`, `GmbH`, `AG`, `B.V.`, `a.s.`, `Ltd`, `Limited`, `SAS`, `AS`). The fuzzy match SHALL tokenize the firm name the same way as the text, so punctuation inside a name (`Alfa-Beta`) does not lower the ratio. A name with no word tokens SHALL never fuzzy-match. A short word (a core or alias of one word token and fewer than 8 letters) SHALL match only when its first letter in the text is upper case, or lower case where the registry writes it so, and SHALL never fuzzy-match. A core shared by several firms SHALL be used as a bare pattern only by the single firm of the highest type precedence (`brokerage_house`, `brokerage_bank`, `foreign_branch`, `foreign_no_branch`). Matching a 20,000-character text against a registry of 1,000 firms SHALL take under 1 second. When the registry file cannot be read, the error SHALL tell the operator to set `REGISTRY_CSV`.

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

#### Scenario: No match
- **WHEN** no name, alias, domain or fuzzy candidate reaches the threshold
- **THEN** no firm is matched

#### Scenario: Registry file missing or malformed
- **WHEN** `REGISTRY_CSV` points to a missing file or a file without the required columns
- **THEN** startup fails with an error naming the file, never silently with an empty registry

#### Scenario: Hyphenated firm name
- **WHEN** the registry holds `Alfa-Beta Inwestycje S.A.` and the text says `Alfa-Beta Inwestycji`
- **THEN** that firm is matched by fuzzy match

#### Scenario: Registry path not set
- **WHEN** `REGISTRY_CSV` points to a missing file
- **THEN** the error names the file and `REGISTRY_CSV`

#### Scenario: Foreign legal form stripped
- **WHEN** the registry holds `Admiral Markets AS` and the text mentions `Admiral Markets`
- **THEN** that firm is matched by name with confidence at least 0.9

#### Scenario: Short word in lower case never matches
- **WHEN** the registry holds `EXT Ltd` and `Nova AG`, and the text says `next step` and `bossa nova`
- **THEN** neither firm is matched

#### Scenario: Short brand matched as a capitalized word
- **WHEN** the registry holds `XTB S.A.` and the text says `Otwórz konto w XTB`
- **THEN** that firm is matched by name with evidence `XTB`

#### Scenario: Shared core goes to the Polish firm
- **WHEN** the registry holds the brokerage house `XTB S.A.` and the foreign firm without a branch `XTB Ltd`, and the text says `XTB`
- **THEN** `XTB S.A.` is matched

#### Scenario: Short core matched by its full name
- **WHEN** the registry holds `Nova AG` and the text says `Nova AG`
- **THEN** that firm is matched by name

#### Scenario: Multi-word core still fuzzy-matches
- **WHEN** the registry holds `Wise Assets Europe AS` and the text says `Wise Asets Europe`
- **THEN** that firm is matched by fuzzy match

#### Scenario: Firm without domains
- **WHEN** a firm has an empty `website_domains` and the page host is any host
- **THEN** that firm is never matched by domain, only by name, alias or fuzzy match

#### Scenario: Real-size registry within budget
- **WHEN** a registry of 1,000 firms matches a 20,000-character text
- **THEN** the match returns in under 1 second
