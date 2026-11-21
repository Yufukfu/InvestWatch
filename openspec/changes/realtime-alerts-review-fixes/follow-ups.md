# Follow-ups: realtime-alerts-review-fixes

From the group 7 review (`iw-reviewer`, range 5b4e5ff..91b0e0d). One disposition each.

| Item | Disposition |
|---|---|
| When `AlertsPage` unmounts, `AlertToasts`' cleanup calls `release` after the hook's cleanup, so new 20 s timers are set on an unmounted hook (harmless with React 18) | new-item |
| A toast that comes back under a pointer that has not moved gets no `mouseenter`, so it is not held | wont-fix: the browser fires no event to react to, and the toast still times out normally |
| `proposal.md` says the toast placement is not changed here, but tasks 6.1 and 7 change it | docs: refresh the proposal before archiving |
