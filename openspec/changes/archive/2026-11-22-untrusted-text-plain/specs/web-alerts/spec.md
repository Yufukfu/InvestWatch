## ADDED Requirements

### Requirement: Toast title has its own direction
The toast title SHALL be rendered as plain text in an element that holds only the title and has `dir="auto"`, so a bidi control in the title cannot reorder the toast's labels.

#### Scenario: Right-to-left override in a title
- **WHEN** a high-risk alert's title contains U+202E
- **THEN** the title element has `dir="auto"`, its text is exactly the title, and `Wysokie ryzyko` and the buttons are outside it
