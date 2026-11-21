## MODIFIED Requirements

### Requirement: R1 firm identification
R1 checks the official name of the investment firm (ZASÓB R1, "oficjalną nazwę firmy inwestycyjnej"). R1 SHALL pass when an official form of the matched firm appears in the text, quoting it: its registry `name`, a ` – ` line of it, or their core without legal forms. It SHALL be `uncertain` when only an entry of the `aliases` column appears. It SHALL fail when no firm is matched or no name or alias of it is in the text.

#### Scenario: Name present
- **WHEN** the text contains `Konto Premium Alfa Inwestycje` and the Alfa firm is matched
- **THEN** R1 is `pass` with evidence `Alfa Inwestycje`

#### Scenario: Matched by domain only
- **WHEN** the firm was matched only by the page domain and its name is absent from the text
- **THEN** R1 is `fail`

#### Scenario: Only a former or trade name used
- **WHEN** the registry holds `CERES DOM INWESTYCYJNY S.A.` with alias `EFIX DOM MAKLERSKI S.A.`, and the text names only `EFIX Dom Maklerski S.A.`
- **THEN** R1 is `uncertain` with evidence `EFIX Dom Maklerski S.A.`
- **AND** the explanation starts with `W materiale użyto nazwy nieoficjalnej/dawnej` and names `CERES DOM INWESTYCYJNY S.A.`

#### Scenario: Official name beats an alias in the same text
- **WHEN** the text names both the alias `Alfa Inwestycje DM` and the official `Alfa Inwestycje Dom Maklerski S.A.`
- **THEN** R1 is `pass` quoting the official form

#### Scenario: Bank brokerage unit line is official
- **WHEN** the registry holds `mBANK S.A. – Biuro Maklerskie mBank` and the text names `Biuro Maklerskie mBank`
- **THEN** R1 is `pass`
