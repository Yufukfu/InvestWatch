## ADDED Requirements

### Requirement: Untrusted text is escaped plain text
Finding fields written by a model or copied from scraped pages (`title`, `summary`, `rule_results[].explanation`, `rule_results[].evidence`, `advertiser.name`, `advertiser.handle`, the document excerpt and text) SHALL be rendered verbatim as escaped plain text in the findings table and the detail: never as HTML or Markdown, never through `dangerouslySetInnerHTML`, and URLs inside them SHALL NOT become links.

#### Scenario: Markup in evidence and explanation
- **WHEN** a finding's evidence, explanation, summary, title and advertiser name and handle contain `<img src=x onerror=alert(1)>` and `[link](javascript:alert(1))`
- **THEN** both strings are shown literally, no `img` element exists in the detail, and no link with a `javascript:` URL or the text `link` exists

#### Scenario: Bare URL in evidence
- **WHEN** the evidence contains `https://evil.example/x`
- **THEN** it is shown as text and the only links in the detail are the source link and the advertiser profile

### Requirement: Untrusted text has its own direction
Each untrusted value listed above SHALL be shown in an element that holds only that value and has `dir="auto"`, so a quote in any language gets its own direction and a bidi control inside it cannot reorder the UI text around it.

#### Scenario: Right-to-left override
- **WHEN** the evidence, explanation, summary, title, advertiser name or handle contains U+202E
- **THEN** each U+202E is inside an element with `dir="auto"` whose text is exactly that field's value, and the closing quote mark of the evidence and the separator before a collapsed rule's explanation are outside that element

#### Scenario: Title in the table
- **WHEN** a row's title contains U+202E
- **THEN** the title button has `dir="auto"` and its text is exactly the title
