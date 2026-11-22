## ADDED Requirements

### Requirement: Server error detail has its own direction
When a status change is rejected and the API's error has a `detail`, the detail SHALL be shown in an element that holds only the detail and has `dir="auto"` and `lang="en"`, so a bidi control in it cannot reorder the Polish label before it.

#### Scenario: Right-to-left override in the detail
- **WHEN** the API rejects a status change with a `detail` that contains U+202E
- **THEN** the detail element has `dir="auto"` and `lang="en"`, its text is exactly the detail, and `Odpowiedź serwera:` is outside it
