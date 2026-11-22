## ADDED Requirements

### Requirement: Each section is its own page
The dashboard SHALL show exactly one of three pages at a time, chosen by the URL hash: `#przeglad` (summary and trend), `#zgloszenia` (findings filters, list and detail) and `#kalibracja` (calibration panel). The header and its navigation SHALL appear on every page. An empty or unknown hash SHALL show `#przeglad`.

#### Scenario: Calibration page shows only calibration
- **WHEN** the hash is `#kalibracja`
- **THEN** the calibration panel is rendered and neither the findings table nor the summary region is in the document

#### Scenario: Unknown hash falls back to the overview
- **WHEN** the hash is `#nieznana` or empty
- **THEN** the summary and trend are rendered and the `Przegląd` link has `aria-current="location"`

#### Scenario: Navigation follows the hash
- **WHEN** the user activates the `Zgłoszenia` link
- **THEN** the hash is `#zgloszenia`, the findings table is rendered, the summary region is gone and only that link has `aria-current="location"`

### Requirement: Changing page resets scroll and focus
When the page changes, the view SHALL scroll to the top and move focus to the main region, so keyboard and screen-reader users start at the new page.

#### Scenario: Focus moves to the page
- **WHEN** the user follows the `Kalibracja` link
- **THEN** the main region has focus and the window is scrolled to the top

### Requirement: Actions that target the findings switch to them
The triage button and the high-risk toast action SHALL show the findings page, so the finding they open is visible.

#### Scenario: Triage from the overview
- **WHEN** the user activates `Rozpocznij triage` on the overview
- **THEN** the hash becomes `#zgloszenia` and the first new high-risk finding opens in the detail

#### Scenario: Toast action from another page
- **WHEN** a high-risk toast is shown on the calibration page and the user activates its `Pokaż` action
- **THEN** the hash becomes `#zgloszenia` and that finding is open in the detail
