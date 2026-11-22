# Proposal

## Why

After the redesign review the dashboard still reads as one long scrolling page, and several details look dated: underlined text links and ghost buttons, a data-table disclosure jammed against its chart, uneven controls. The request is for real sub-pages and a modern, consistent look across buttons, links, text, filters and components.

## What Changes

- **Sub-pages**: `#przeglad`, `#zgloszenia` and `#kalibracja` each render only their own content (overview: summary and trend; findings: filters, list and detail drawer; calibration: the panel). The header stays on every page. An unknown or empty hash shows the overview. Switching page scrolls to the top and moves focus to the page heading region. The triage button and the toast `Pokaż` action switch to the findings page themselves.
- **UI polish pass** in `web/src/styles.css` (and markup only where needed): no underlines at rest on links or ghost buttons (hover and focus states use colour and a visible focus ring instead), consistent button, input, select, chip and disclosure styling, spacing between a chart and its data-table button, and a deep audit of every section for dated styling.
- Touches no contract, REST route or event; no backend change. Owner: `web/` (see CODEOWNERS).

Out of scope: a router library (hash state stays), a dark theme, new data or features (bulk actions, export: issue #115).

## Capabilities

### New Capabilities
- `web-navigation`: the three sub-pages, their hash addresses and focus and scroll behaviour.

### Modified Capabilities
- `web-design-system`: adds the interaction-styling requirement (no resting underlines, consistent controls, chart-to-button spacing).

## Impact

- `web/src/App.tsx` and its test, `web/src/url/`, `web/src/features/{findings,alerts}/data/` (switch to the findings page), `web/src/styles.css`, small markup changes in components. Overlap: none open on these files.
