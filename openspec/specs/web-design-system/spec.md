# web-design-system Specification

## Purpose

The visual contract of the dashboard (`web/`): the tokens, fonts, colour roles and legibility floors every section follows, so the app reads as one calm institutional tool and passes the production security headers.

## Requirements

### Requirement: Tokens define the visual language
The dashboard SHALL define its colours, spacing, radii and type scale once as CSS custom properties and every section SHALL use them. Red SHALL be used only for high risk, violations and the single triage action; modules SHALL be identified by text (`M1`, `M2`, `M3`), never by a colour that is also a risk colour.

#### Scenario: One definition per value
- **WHEN** the stylesheet is read
- **THEN** each colour, spacing step and radius used by a section is a custom property declared in one place, and no section declares its own hex value for a role that has a token

#### Scenario: Module colour is not a risk colour
- **WHEN** the trend chart draws `M1`, `M2` and `M3`
- **THEN** none of the series uses the high-risk red, and each series also differs by dash pattern and legend label

### Requirement: Fonts are self-hosted
The dashboard SHALL load Space Grotesk, Inter and Geist Mono from its own origin, with the Latin and Latin Extended subsets so every Polish character renders, and SHALL NOT request any font from another origin.

#### Scenario: Production build makes no third-party request
- **WHEN** the production build is opened under its security headers (`font-src 'self'`)
- **THEN** all three families load from the same origin and the console shows no blocked request

#### Scenario: Polish characters
- **WHEN** a title contains `ąćęłńóśźż`
- **THEN** each glyph renders in the chosen family, not in a fallback

### Requirement: Text stays legible
All text SHALL have a contrast ratio of at least 4.5:1 against its background (3:1 for text of 24px or more), and no text SHALL be smaller than 12px. The focus ring and the hover, focus and selected borders of controls SHALL have at least 3:1 against their background; the resting border of a control MAY be softer. Risk, rule result and status SHALL always carry a text label in addition to colour.

#### Scenario: Placeholder and secondary text
- **WHEN** the contrast of placeholder text, secondary labels and text on every coloured fill is measured
- **THEN** each pair meets the ratio above

#### Scenario: Risk without colour
- **WHEN** the page is viewed in greyscale
- **THEN** every risk level, rule result and status is still identifiable from its label

#### Scenario: Soft resting border, strong interaction border
- **WHEN** the stylesheet is parsed
- **THEN** the resting border of buttons, inputs, selects, chips and the data-table button uses the soft token, and the border used on hover and focus has at least 3:1 against the surface

### Requirement: Styling works under the production CSP
Styling SHALL come from the stylesheet. The served HTML SHALL contain no `style` attribute and no inline `<style>` block, so the production policy `style-src 'self'` blocks nothing. A width or position that depends on data (a score bar, a proportion bar) MAY be set through the element's style property from script, which that policy allows.

#### Scenario: Console is clean in the build
- **WHEN** the production build is served with `web/security-headers.conf` and every section is shown (summary, trend, findings with the detail open, a toast, calibration)
- **THEN** the browser console reports no CSP violation and no error, and `index.html` contains no `style` attribute

### Requirement: Layout adapts to the screen
The dashboard SHALL lay itself out from the viewport width at three steps: up to 599px (phone), 600px to 1023px (tablet) and 1024px and wider (desktop). At every width from 320px up the page SHALL NOT scroll horizontally, every button, chip, field, select, pager control and navigation link SHALL be at least 44px by 44px on phone and tablet (a link inside running text is exempt), and the findings list SHALL stay readable without horizontal scrolling inside it.

#### Scenario: No horizontal scroll
- **WHEN** the page is loaded at 320px, 375px, 768px, 1024px, 1280px and 1440px with data in every section and the detail open
- **THEN** the document is not wider than the viewport at any of these widths

#### Scenario: Touch targets
- **WHEN** the viewport is 375px or 768px wide
- **THEN** every button, chip, link-styled control, select, field and pager control has a hit area of at least 44px by 44px, except links inside running text

#### Scenario: Tablet table
- **WHEN** the viewport is 768px wide
- **THEN** the table shows the risk, title, module and score columns, with platform, status and detection time under the title

### Requirement: Phone layout
Below 1024px (phone and tablet, as in the mockups) the filters SHALL collapse behind one "Filtry" control that shows how many are active, each finding SHALL be a card showing risk, module, score, title, platform, status and detection time, and the detail SHALL fill the screen. The summary, trend and calibration SHALL reflow to one column and keep their figures and labels complete.

#### Scenario: Phone filters
- **WHEN** the viewport is 375px wide and two filters are active
- **THEN** the filter fields are hidden behind a "Filtry" control labelled with the number 2, activating it shows them, and the findings are cards

#### Scenario: Detail on a phone
- **WHEN** a finding is opened at 375px
- **THEN** the detail fills the screen, its close control stays reachable without scrolling, and `Esc` or the close control returns to the list at the same scroll position

#### Scenario: Calibration on a phone
- **WHEN** the calibration panel is shown at 375px
- **THEN** the slider spans the full width, the metrics are listed in two columns with their current values beside them, and the chart keeps its axes and both markers readable

### Requirement: Visible focus and reduced motion
Every interactive element SHALL show a visible focus indicator of at least 2px, and any animation SHALL be disabled when the user prefers reduced motion.

#### Scenario: Keyboard focus is visible
- **WHEN** the user tabs through the header, filters, table, drawer and calibration controls
- **THEN** each focused element shows the focus indicator

#### Scenario: Reduced motion
- **WHEN** the operating system asks for reduced motion
- **THEN** the live badge, toasts and the drawer appear without animation

### Requirement: Modern interaction styling
Links, ghost buttons and disclosure controls SHALL NOT be underlined at rest; hover and keyboard focus SHALL be shown with colour change and the visible focus ring. Buttons, inputs, selects, chips and disclosure summaries SHALL share one radius, height and border treatment from the tokens. A data-table disclosure SHALL have at least 16px of space above it.

#### Scenario: No resting underline
- **WHEN** the stylesheet is parsed
- **THEN** no rule outside `:hover` or `:focus-visible` sets `text-decoration` to `underline` on `a`, `.link`, `.btn-ghost` or a disclosure summary

#### Scenario: Data table button is separated from its chart
- **WHEN** a chart is followed by `Pokaż dane w tabeli`
- **THEN** the disclosure's top margin is at least 16px

### Requirement: Pager buttons look alike
The previous-page and next-page buttons SHALL have the same colours whether they are enabled or disabled; a disabled pager button SHALL use the `disabled` attribute and the not-allowed cursor, not a faded colour.

#### Scenario: First page
- **WHEN** the findings list is on page 1
- **THEN** `Poprzednia strona` is disabled and has the same opacity as the enabled `Następna strona`
