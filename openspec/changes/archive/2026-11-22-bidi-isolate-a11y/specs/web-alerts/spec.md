## ADDED Requirements

### Requirement: Alert title is bidi-isolated in screen-reader text
Wherever the alert title is put into a string next to UI text (the toast's `aria-label`, the `Zamknij` button's `aria-label` and the polite live-region announcement), the title SHALL be wrapped in U+2068 (FIRST STRONG ISOLATE) and U+2069 (POP DIRECTIONAL ISOLATE), so a bidi control in the title cannot reorder the label around it.

#### Scenario: Right-to-left override in a title
- **WHEN** `finding.high_risk` arrives with a title that contains U+202E
- **THEN** the toast's accessible name is `Wysokie ryzyko: ` followed by U+2068, the title and U+2069, its `Zamknij` button's name is `Zamknij: ` followed by the same isolated title, and the live region reads `Wysokie ryzyko: ` followed by the same isolated title
