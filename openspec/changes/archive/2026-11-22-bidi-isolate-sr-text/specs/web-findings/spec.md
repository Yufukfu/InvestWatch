## ADDED Requirements

### Requirement: Server error detail has its own direction
When a status change is rejected and the API returns its own error text, that text SHALL be shown alone in an element with `dir="auto"` (and `lang="en"`), outside the Polish label `Odpowiedź serwera:`, so a bidi control in it cannot reorder the label.

#### Scenario: Right-to-left override in the server detail
- **WHEN** the API rejects a status change with an error text that contains U+202E
- **THEN** the text is shown in an element with `dir="auto"` whose text is exactly the error text, and `Odpowiedź serwera:` is outside that element
