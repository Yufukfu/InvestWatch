## ADDED Requirements

### Requirement: Modern interaction styling
Links, ghost buttons and disclosure controls SHALL NOT be underlined at rest; hover and keyboard focus SHALL be shown with colour change and the visible focus ring. Buttons, inputs, selects, chips and disclosure summaries SHALL share one radius, height and border treatment from the tokens. A data-table disclosure SHALL have at least 16px of space above it.

#### Scenario: No resting underline
- **WHEN** the stylesheet is parsed
- **THEN** no rule outside `:hover` or `:focus-visible` sets `text-decoration` to `underline` on `a`, `.link`, `.btn-ghost` or a disclosure summary

#### Scenario: Data table button is separated from its chart
- **WHEN** a chart is followed by `Pokaż dane w tabeli`
- **THEN** the disclosure's top margin is at least 16px
