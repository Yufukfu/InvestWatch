# Follow-ups: calibration-panel

From the whole-branch `iw-reviewer` pass. Fixed in this branch:
- status changes now refresh the calibration (PATCH and `finding.updated`), and the web rules say so
- save feedback is reset on a module switch
- off-curve current threshold: compare by index and label the nearest point
- the selection is kept as a threshold, not a position
- task 3.1 text corrected
- the save button is described by the warning

| Item | Disposition |
|---|---|
| `aria-valuetext` uses a dot (`próg 0.70`) while percentages use a comma | wont-fix: thresholds are shown as the API's decimal everywhere in the panel and the docs |
| The `Zapisano` status appears only after a save, so some screen readers may not announce it | wont-fix for now: the button's state and the new current threshold also change; revisit with a persistent live line like the alerts |
| The demo script says M2 0.5 to 0.7, which changes no risk level on the mock scores | docs: noted in the AI log and task 3.1; the demo plan (analytics-plan §8) belongs to Damian, tell him before the rehearsal |
