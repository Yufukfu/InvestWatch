## ADDED Requirements

### Requirement: Status shortcuts never discard unsaved edits
The `1`-`5` status shortcuts SHALL do nothing while the status editor of the open finding has unsaved changes (a status choice or a note that differs from the saved values).

#### Scenario: Unsaved note
- **WHEN** the analyst has typed a note, moved focus to `Zapisz decyzję` and presses `3`
- **THEN** no request is sent and the note stays in the editor
