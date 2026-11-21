# web-calibration Specification

## Purpose

The threshold calibration panel of the dashboard (`web/`): preview the precision/recall trade-off of a module threshold from `GET /calibration`, and save it with `PUT /settings/thresholds`. Values come from the backend and are not recalculated in the browser.

## Requirements

### Requirement: Choose a module and a threshold
The panel SHALL let the user choose a module (`M1`, `M2`, `M3`; `M2` first) and load `GET /calibration?module=<module>`. A keyboard-operable slider labelled in Polish SHALL move only between the `threshold` values of the returned points and SHALL start at the point nearest `current_threshold`.

#### Scenario: Default view
- **WHEN** the panel loads with `contracts/mocks/calibration-M2.json`
- **THEN** M2 is selected and the slider shows 0.50 as both the current and the selected threshold

#### Scenario: Another module
- **WHEN** the user switches to M3
- **THEN** `GET /calibration?module=M3` is requested and the slider starts at M3's `current_threshold`

### Requirement: Show the selected point against the current one
For the selected point the panel SHALL show `tp`, `fp`, `fn`, `tn`, `precision`, `recall` and `f1` when present, exactly as returned. Each value SHALL be shown next to the same value at the current threshold, and the panel SHALL state `labeled_samples`. Moving the slider SHALL NOT send a request.

#### Scenario: Moving the slider
- **WHEN** the user moves the M2 slider to 0.70
- **THEN** TP, FP, FN, TN, precision and recall show the 0.7 point's values next to the values at 0.50, and no request is sent

### Requirement: Calibration chart with a text alternative
The panel SHALL draw precision and recall against the threshold for the returned points, distinguishable by colour and dash pattern, with the current and the selected thresholds marked. It SHALL offer the same points as a table. The chart component SHALL take its data as props and SHALL NOT fetch.

#### Scenario: Chart and table
- **WHEN** the M2 curve is shown
- **THEN** the chart's accessible name names precision and recall, and a table lists every point's threshold, precision, recall, FP and FN

### Requirement: Save is explicit and global
The panel SHALL send `PUT /settings/thresholds` only when the user presses `Zapisz próg`. The body SHALL be the thresholds from `GET /settings/thresholds` with only the selected module replaced. The button SHALL be disabled while the selected threshold equals the current one or a save is running. The panel SHALL warn that saving changes the risk level of every finding and the alert threshold.

#### Scenario: Save body
- **WHEN** the user selects M2 0.70 and presses `Zapisz próg`
- **THEN** the PUT body is `{ "M1": 0.6, "M2": 0.7, "M3": 0.7 }` (from the thresholds mock)

#### Scenario: Nothing to save
- **WHEN** the selected threshold equals the current one
- **THEN** `Zapisz próg` is disabled

### Requirement: After a save
After a successful save the dashboard SHALL refetch findings, stats, calibration and settings, so the panel shows the new current threshold and the list shows the recomputed risk levels. On a rejected save it SHALL show a Polish error and keep the current threshold.

#### Scenario: Saved
- **WHEN** the PUT succeeds
- **THEN** the findings list and summary are requested again and the panel shows 0.70 as the current threshold

#### Scenario: Rejected save
- **WHEN** the PUT answers 422
- **THEN** an alert says in Polish that the threshold was not saved, and the current threshold is unchanged

### Requirement: Empty and error states
The panel SHALL say in Polish when the calibration cannot be loaded and when a module has no points or no labelled samples. It SHALL then offer no slider and no save.

#### Scenario: No labelled data
- **WHEN** `GET /calibration` returns `labeled_samples` 0 or an empty `points` list
- **THEN** the panel says there is not enough labelled data for this module and shows no slider

#### Scenario: Load error
- **WHEN** `GET /calibration` fails
- **THEN** an alert says the calibration could not be loaded, and the module switch stays usable
