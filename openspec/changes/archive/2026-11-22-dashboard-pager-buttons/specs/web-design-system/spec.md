## ADDED Requirements

### Requirement: Pager buttons look alike
The previous-page and next-page buttons SHALL have the same colours whether they are enabled or disabled; a disabled pager button SHALL use the `disabled` attribute and the not-allowed cursor, not a faded colour.

#### Scenario: First page
- **WHEN** the findings list is on page 1
- **THEN** `Poprzednia strona` is disabled and has the same opacity as the enabled `Następna strona`
