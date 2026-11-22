# Design

Deep link: the hash is only trusted when it names a page. Otherwise `hasFindingsParams(search)` (a list of the findings parameter names, defined next to `goToSection`) picks the findings page, and `history.replaceState` writes the hash so the navigation matches and the back button does not gain an entry. An explicit hash always wins (`#kalibracja?finding=` stays on calibration).

Shortcut: the editor reports whether it has unsaved changes through an `onDirtyChange` callback; the detail container keeps it in the shortcut target. Ignoring the key is the smaller fix than saving the draft note with the status (the reviewer's alternative), and it never writes data the analyst did not submit.
