# web-alerts Specification

## Purpose

Real-time behaviour of the dashboard (`web/`): one Socket.IO connection to `/events`, cache updates from the finding events of `.docs/integration-plan.md` §6, the high-risk toast and the connection indicator.

## Requirements

### Requirement: One live connection
The dashboard SHALL open exactly one Socket.IO connection to namespace `/events` on path `/socket.io` of the same origin for the whole app, and SHALL show its state in the header as text: `Na żywo` when connected, `Łączenie…` while connecting, `Brak połączenia na żywo` after a disconnect or connection error. On every connect and reconnect it SHALL refetch the findings list and the stats, because events published while disconnected are lost.

#### Scenario: Connected
- **WHEN** the socket connects
- **THEN** the header shows `Na żywo` and the findings and stats queries are refetched

#### Scenario: Connection lost
- **WHEN** the socket disconnects or fails to connect
- **THEN** the header shows `Brak połączenia na żywo` and the rest of the dashboard keeps working over REST

#### Scenario: Single connection
- **WHEN** the app renders
- **THEN** one socket is created, and it is closed when the app unmounts

### Requirement: Events update the cached data
On `finding.created` and `finding.high_risk` the dashboard SHALL invalidate the findings and stats data so they refetch, and SHALL NOT insert rows from the event payload. On `finding.updated` it SHALL set the new status on that finding in every cached findings list and in its cached detail, and SHALL refetch the stats. Payloads whose `id` is not a UUID (or without a valid `status` for `finding.updated`) SHALL be ignored; a high-risk payload without a `title` still refreshes but raises no toast.

#### Scenario: New finding
- **WHEN** a `finding.created` event arrives
- **THEN** the findings list and the summary are requested again

#### Scenario: Status changed in another tab
- **WHEN** `finding.updated` arrives with `{ id, status: "confirmed" }` for a finding in the visible list
- **THEN** its row shows `Potwierdzone` without a list refetch

#### Scenario: Malformed event
- **WHEN** `finding.updated` arrives with `{ id }` and no status, or any finding event arrives with no id or an id that is not a UUID
- **THEN** nothing changes and nothing throws

### Requirement: High-risk toast
On `finding.high_risk` the dashboard SHALL show a toast with the label `Wysokie ryzyko`, the finding title rendered as text, the module and the score, a `Pokaż` button that opens that finding's detail, and a `Zamknij` button, and SHALL announce the label and title through a polite live region. Toasts SHALL not take focus, SHALL disappear after 20 seconds unless hovered or focused, SHALL show at most 4 at a time with the newest first, and SHALL show one toast per finding id.

#### Scenario: Toast content
- **WHEN** `finding.high_risk` arrives for `{ id, module: "M3", score: 0.93, title }`
- **THEN** a toast shows `Wysokie ryzyko`, the title, `M3` and `0.93`

#### Scenario: Open from the toast
- **WHEN** the user presses `Pokaż`
- **THEN** the URL gets `finding=<id>`, the detail panel opens, and the toast is dismissed

#### Scenario: Untrusted title
- **WHEN** the title contains `<img src=x onerror=alert(1)>`
- **THEN** it is shown literally and no element is created

#### Scenario: Held toast
- **WHEN** the pointer or keyboard focus is on a toast when its 20 seconds run out
- **THEN** it stays, and its 20 seconds start again when both leave

#### Scenario: Limits
- **WHEN** six different high-risk events arrive, and one of them twice
- **THEN** four toasts are visible, newest first, with no duplicate id, and each disappears after 20 seconds unless dismissed earlier

### Requirement: Toast title has its own direction
The toast title SHALL be rendered as plain text in an element that holds only the title and has `dir="auto"`, so a bidi control in the title cannot reorder the toast's labels.

#### Scenario: Right-to-left override in a title
- **WHEN** a high-risk alert's title contains U+202E
- **THEN** the title element has `dir="auto"`, its text is exactly the title, and `Wysokie ryzyko` and the buttons are outside it

### Requirement: Alert title is bidi-isolated in screen-reader text
Wherever the alert title is put into a string next to UI text (the toast's `aria-label`, the `Zamknij` button's `aria-label` and the polite live-region announcement), the title SHALL be wrapped in U+2068 (FIRST STRONG ISOLATE) and U+2069 (POP DIRECTIONAL ISOLATE), so a bidi control in the title cannot reorder the label around it.

#### Scenario: Right-to-left override in a title
- **WHEN** `finding.high_risk` arrives with a title that contains U+202E
- **THEN** the toast's accessible name is `Wysokie ryzyko: ` followed by U+2068, the title and U+2069, its `Zamknij` button's name is `Zamknij: ` followed by the same isolated title, and the live region reads `Wysokie ryzyko: ` followed by the same isolated title
