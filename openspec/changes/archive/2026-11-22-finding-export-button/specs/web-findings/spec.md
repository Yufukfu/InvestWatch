## ADDED Requirements

### Requirement: Export a finding's evidence pack
The finding detail SHALL offer an `Eksportuj` link that opens the printable evidence pack of that finding, `GET /findings/{id}/export?format=html` (contracts 1.2.0), under the app's API base URL, in a new tab. The link SHALL be shown only while that finding's detail is loaded, and it SHALL be keyboard-reachable inside the modal detail.

#### Scenario: Loaded detail
- **WHEN** the detail of a finding is loaded
- **THEN** the header shows a link named `Eksportuj` whose `href` is `<API base>/findings/<id>/export?format=html` and which opens in a new tab with `rel="noopener noreferrer"`

#### Scenario: Not loaded or unknown
- **WHEN** the detail is still loading, failed to load with no earlier data, or the finding does not exist (404)
- **THEN** no `Eksportuj` link is shown

## MODIFIED Requirements

### Requirement: Untrusted text is escaped plain text
Finding fields written by a model or copied from scraped pages (`title`, `summary`, `rule_results[].explanation`, `rule_results[].evidence`, `advertiser.name`, `advertiser.handle`, the document excerpt and text) SHALL be rendered verbatim as escaped plain text in the findings table and the detail: never as HTML or Markdown, never through `dangerouslySetInnerHTML`, and URLs inside them SHALL NOT become links.

#### Scenario: Markup in evidence and explanation
- **WHEN** a finding's evidence, explanation, summary, title and advertiser name and handle contain `<img src=x onerror=alert(1)>` and `[link](javascript:alert(1))`
- **THEN** both strings are shown literally, no `img` element exists in the detail, and no link with a `javascript:` URL or the text `link` exists

#### Scenario: Bare URL in evidence
- **WHEN** the evidence contains `https://evil.example/x`
- **THEN** it is shown as text and the only links in the detail are the export link, the source link and the advertiser profile
