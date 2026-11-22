## MODIFIED Requirements

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
