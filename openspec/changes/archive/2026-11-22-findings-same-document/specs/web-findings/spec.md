## ADDED Requirements

### Requirement: Rows show the source host
Each findings row SHALL show the host of the finding's `url` as text, and the list SHALL keep one row per finding, never merged or deduplicated by URL or document.

#### Scenario: Host as text
- **WHEN** a finding's `url` is `https://example.com/post/1?x=<b>`
- **THEN** its row shows `example.com` as text

#### Scenario: Unusable URL
- **WHEN** a finding's `url` is not an http(s) URL
- **THEN** its row shows no host and the rest of the row is unchanged

#### Scenario: Two modules on one post in the list
- **WHEN** the response holds an M1 and an M3 finding with the same `document_id`
- **THEN** both are shown as separate rows, each with its own status

### Requirement: Detail shows every module of the material
When a finding's detail is open, the dashboard SHALL load the findings of the same document with `GET /findings?document_id=<document_id>` and, when there is more than one, SHALL show a keyboard-operable module switcher listing each module with its risk level as text. Choosing a module SHALL set `finding=<id>` in the URL and show that finding's rules, score, risk and analyst decision, while the source, excerpt and screenshot stay shown once.

#### Scenario: Switch from M1 to M3
- **WHEN** the detail of an M1 finding is open and its document also has an M3 finding
- **THEN** the switcher shows `M1` (current) and `M3`, and activating `M3` sets `finding=<M3 id>`, shows the M3 rules and decision, and keeps focus on the switcher

#### Scenario: Single module
- **WHEN** the document has only the open finding
- **THEN** no switcher is shown

#### Scenario: Sibling request fails
- **WHEN** the `GET /findings?document_id=…` request fails
- **THEN** no switcher is shown, the detail of the open finding stays fully usable, and no error replaces it

#### Scenario: Deep link and back
- **WHEN** the user switches from M1 to M3 and presses the browser back button
- **THEN** the M1 detail is shown again

#### Scenario: Module filter does not hide siblings
- **WHEN** the list is filtered to `M1` and the user opens an M1 finding whose document also has M3
- **THEN** the switcher still offers `M3`, because the sibling request carries no module filter
