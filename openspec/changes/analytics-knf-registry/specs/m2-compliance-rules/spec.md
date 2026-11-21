## MODIFIED Requirements

### Requirement: R1 firm identification
R1 checks the official name of the investment firm (ZASÓB R1, "oficjalną nazwę firmy inwestycyjnej"). The official forms of a firm are its registry `name`, each ` – `-separated line of that name (a bank and its brokerage unit), and the core of each of these without legal forms. Every entry of the registry's `aliases` column (former names, trade names, abbreviations, `DM` and case forms) is unofficial. R1 SHALL pass when an official form of the matched registry firm appears in the text, quoting it. It SHALL be `uncertain` when only an unofficial alias appears, quoting it, with an explanation that starts with `W materiale użyto nazwy nieoficjalnej/dawnej` and names the official name. It SHALL fail when no registry firm is matched or neither its name nor an alias is in the text.

#### Scenario: Name present
- **WHEN** the text contains `Konto Premium Alfa Inwestycje` and the Alfa firm is matched
- **THEN** R1 is `pass` with evidence `Alfa Inwestycje`

#### Scenario: Matched by domain only
- **WHEN** the firm was matched only by the page domain and its name is absent from the text
- **THEN** R1 is `fail`

#### Scenario: Only a former or trade name used
- **WHEN** the registry holds `CERES DOM INWESTYCYJNY S.A.` with alias `EFIX DOM MAKLERSKI S.A.`, and the text names only `EFIX Dom Maklerski S.A.`
- **THEN** R1 is `uncertain` with evidence `EFIX Dom Maklerski S.A.` and an explanation starting `W materiale użyto nazwy nieoficjalnej/dawnej` that names `CERES DOM INWESTYCYJNY S.A.`

#### Scenario: Official name beats an alias in the same text
- **WHEN** the text names both the alias `Alfa Inwestycje DM` and the official `Alfa Inwestycje Dom Maklerski S.A.`
- **THEN** R1 is `pass` quoting the official form

#### Scenario: Bank brokerage unit line is official
- **WHEN** the registry holds `mBANK S.A. – Biuro Maklerskie mBank` and the text names `Biuro Maklerskie mBank`
- **THEN** R1 is `pass`
