## ADDED Requirements

### Requirement: Title is isolated in screen-reader strings
Where the alert title is joined with UI text in one string (the toast's and the close button's accessible names, the polite live announcement), the title SHALL be wrapped in U+2068 (FSI) and U+2069 (PDI) and balanced first, so that no bidi control in the title can end the isolate. All other characters of the title are kept.

#### Scenario: Right-to-left override in the accessible names
- **WHEN** a high-risk alert's title contains U+202E
- **THEN** the toast's accessible name is `Wysokie ryzyko: ` followed by FSI, the title and PDI, and the close button's name is `Zamknij: ` followed by FSI, the title and PDI

#### Scenario: Right-to-left override in the announcement
- **WHEN** `finding.high_risk` arrives with a title that contains U+202E
- **THEN** the live announcement is `Wysokie ryzyko: ` followed by FSI, the title and PDI

#### Scenario: Title that tries to close the isolate
- **WHEN** the title contains a PDI before a U+202E, or opens an isolate it never closes, or contains a line break
- **THEN** the stray PDI is dropped, the open isolate is closed before the final PDI, the line break becomes a space, and the U+202E stays between FSI and the final PDI
