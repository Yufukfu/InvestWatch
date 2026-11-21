# Design

## Context

See proposal.md. Rules for the panel are in `.claude/rules/web-dashboard.md` ("Calibration panel"). The slider only selects points of `GET /calibration`, so nothing is recalculated in the browser. The PUT is a global write. The generated `putSettingsThresholds` invalidates only `settings`, so an override must add `findings`, `stats` and `calibration`. Layering follows [ADR 0204](../../../.docs/decisions/0204-frontend-architecture.md).

## Decisions

- **Slider over point indexes**, not raw numbers. It is a native `<input type="range">` from 0 to `points.length - 1`, with `aria-valuetext="próg 0.70"`. Every position is a real point, so there is no interpolation and no browser maths. The start index is the point with the smallest `|threshold - current_threshold|`, which is a selection, not a metric.
- **State in the page component:** the module and the selected index are local UI state in `CalibrationPage`. They are not in the URL, because a preview is not a shareable view. The `key` is module plus current threshold, so a save or module switch resets the slider to the new current point.
- **Body of the PUT:** taken from `GET /settings/thresholds` with one module replaced. The panel never invents the other modules' values. Save stays disabled until the settings have loaded.
- **Lazy-loaded section**, like the trend. Recharts lives in the lazy chunk, and the calibration chunk reuses it.
- **Comparison display:** the current value is shown beside the selected one (`FP 23 → 12`). The arrow direction comes from comparing two returned numbers, and no new metric is derived.

## Risks / Trade-offs

- A threshold that is not on the curve (set elsewhere): the slider starts at the nearest point, and the panel shows the exact `current_threshold` as the current value.
- A save recomputes every `risk_level` and the alert threshold, and it can be undone only by saving again. The warning text and the explicit button mitigate this.
