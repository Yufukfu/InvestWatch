# Tasks

## 1. Tokens, fonts and base type

- [x] 1.1 Write the failing tests first: a contrast test that parses the token colours and fails below 4.5:1 for every text-on-fill pair used (placeholder, secondary text, text on risk pills, white on the amber and red fills), a check that non-text controls (borders, focus ring, slider) are at least 3:1, a test that `index.html` has no `style` attribute, and a test that `main.tsx` imports only `latin` and `latin-ext` font files
- [x] 1.2 Add `@fontsource/space-grotesk`, `@fontsource/inter` and `@fontsource/geist-mono` (the variable packages cannot be limited to two subsets), run `npm audit`, import the used weights and subsets in `main.tsx`
- [x] 1.3 Replace the `:root` values in `styles.css` with the tokens from the Paper page (colour roles, spacing 4/8 steps, radii, type scale, 2px focus ring, reduced-motion rule) and set Inter as the body font
- [ ] 1.4 Run `npm run typecheck`, `npm run lint`, `npm test` and `npm run build`; open the build and confirm all three families load from the same origin with a clean console
- [x] 1.5 mutations: 12 tried, 12 caught

## 2. Header, hero summary and navigation

- [x] 2.1 Update the `SummaryCards`/`App` tests first: header shows `NARZĘDZIE NADZORCZE` and three anchor links, the hero shows `72` and `10` from the summary with the labels `zgłoszeń` and `wysokiego ryzyka`, the module counts are listed
- [x] 2.2 Restyle the header, live and health badges (green live dot), hero and module counts; anchors scroll to the section ids
- [x] 2.3 mutations: 12 tried, 12 caught

## 3. Trend and findings table, filters and phone cards

- [x] 3.1 Update tests first: high-risk rows carry the tint class and the text label `Wysoki`, scores and dates render in the mono class, M3 series colour is not the high-risk red and series still differ by dash pattern, the phone filter button has `aria-expanded`, controls the filter region and shows the active-filter count
- [x] 3.2 Restyle the trend (colours, legend, bucket switch at 44px) and the filters (labels, chips, 44px controls, "Filtry" disclosure with count below 600px)
- [x] 3.3 Restyle the findings table: tinted high-risk rows, mono scores and dates, tablet layout with platform, status and time under the title, phone layout as cards from the same markup with table roles kept
- [x] 3.4 Run the web suite; confirm no horizontal overflow of the page at 320, 375, 768 and 1024px against the mock server
- [x] 3.5 mutations: 14 tried, 14 caught

## 4. Detail drawer, alert toast and status editor

- [x] 4.1 Confirm the existing tests already cover what the detail shows (firm, advertiser, the "Dlaczego to zgłoszenie" text, each rule with legal basis and evidence, the status editor) and that focus stays in the dialog and `Esc` returns it to the row; no new unit test is red. The status editor keeps its native `<select>` (44px) instead of chips: it is keyboard-operable and a chip rewrite would change nine tests for no behavioural gain. Full-screen below 600px is CSS only (design decision 3: no `matchMedia`, so there is no class to assert); it is measured in the browser in task 8.2
- [x] 4.2 Restyle the drawer (full-screen on phone, side panel from 600px), rule list with severity bars, status editor and the toast (44px actions, reduced-motion safe)
- [x] 4.3 mutations: n/a, CSS-only restyle with no logic (layout is measured in the browser in 8.2)

## 5. Calibration panel

- [x] 5.1 Update tests first: a proportion bar with TP, FN, FP and TN segments whose widths follow the returned counts and whose labels carry the counts as text; metrics show their value beside the current one; slider spans the full width on phone
- [x] 5.2 Restyle the calibration panel (module switch at 44px, large threshold figure, proportion bar, metric grid with two columns on phone, chart markers legible, warning and save bar)
- [x] 5.3 mutations: 7 tried, 7 caught

## 6. Triage entry

- [ ] 6.1 Write the failing tests first: with 10 high-risk findings the hero button reads `Rozpocznij triage: 10 do oceny`, activating it from page 3 with a module, text and date filter set clears those, sets `status=new` and `risk_level=high`, and opens the first returned finding; the button shows no count; with 0 high-risk findings the button is absent; an empty or failed list opens no detail and clears the one-shot flag
- [ ] 6.2 Implement the button and the URL update through the existing `findingsUrl` helpers and the summary hook
- [ ] 6.3 mutations: N tried, N caught

## 7. Keyboard shortcuts

- [ ] 7.1 Write the failing tests first: `J`/`K` move the selection, `J` with nothing selected selects the first row, `K` on the first row stays, `3` sends a `PATCH` with `confirmed` and the finding stays selected, `3` on an already confirmed finding sends nothing, `1` with no detail open sends nothing, typing `1` in the search field sends nothing, a modifier key is ignored, `J` on the last row does nothing, a failed `PATCH` shows the normal error, `O` does nothing for a non-http URL, `/` focuses search, `Esc` closes the detail once (the shortcuts do not also handle it), and the legend disclosure lists every shortcut
- [ ] 7.2 Implement `useFindingShortcuts` and the shortcut legend disclosure
- [ ] 7.3 mutations: N tried, N caught

## 8. Responsive evidence

- [ ] 8.1 Build the production bundle and serve it with the contract mock server; capture every section, plus the open detail, a toast and the calibration panel, at 320, 375, 768, 1024, 1280 and 1440px with Chrome DevTools against the contract mock server (`web/README.md`) and save them under `.docs/screens/dashboard-redesign/`; export the Paper desktop, tablet and mobile artboards to `.docs/screens/dashboard-redesign/design/`
- [ ] 8.2 Confirm programmatically at each width that `document.documentElement.scrollWidth` does not exceed the viewport width and that no interactive element is smaller than 44px by 44px at 375 and 768px
- [ ] 8.3 Have a subagent review the saved screenshots against the exported Paper artboards, including a greyscale pass for risk, rule result and status labels and a check that `ąćęłńóśźż` render in the chosen fonts, and list defects; verify each against the code, fix the real ones and recapture
- [ ] 8.4 Check the browser console is clean in the production build at every width (no CSP violation, no error)

## 9. Closing tasks

- [ ] 9.1 Apply the `iw-docs-update` skill (update `web/CLAUDE.md` if its rules changed, `.docs/status/dashboard.md` for the redesign, any ADR needed for the font dependencies), run `docs-check`, and add the `iw-ai-log` row
- [ ] 9.2 Run the `iw-pr-review` skill and fix real findings
- [ ] 9.3 Raise the bulk actions, export and M2 coverage strip as an issue assigned to Damian, noting that contracts are frozen
