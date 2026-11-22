## ADDED Requirements

### Requirement: Re-scan state in the finding detail
The finding detail SHALL show the re-scan state that `GET /findings/{id}` serves as `document.scrape_meta.rescan` (`rest-api` "Finding detail with its document"): a text badge `Zmieniona` with a Polish line naming `latest_document_id` for `changed`, a text badge `Usunięta` with a Polish line for `removed`, each with `checked_at` in UTC, and nothing otherwise. The web SHALL parse `scrape_meta` as untrusted data and show only a known state, a UUID id and a valid timestamp.

#### Scenario: Page changed after the finding
- **WHEN** the detail has `rescan` `{state: "changed", latest_document_id: <uuid>, checked_at: <time>}`
- **THEN** the panel shows the badge `Zmieniona`, a line naming `<uuid>` as the newer version, and the check time in UTC

#### Scenario: Page removed after the finding
- **WHEN** the detail has `rescan` `{state: "removed", latest_document_id: null, checked_at: <time>}`
- **THEN** the panel shows the badge `Usunięta` and a line that the page was removed

#### Scenario: No re-scan data (mock mode)
- **WHEN** the detail comes from `contracts/mocks/finding-detail.json`, which has no `scrape_meta.rescan`, or `rescan.state` is `current`
- **THEN** the panel shows no re-scan badge or line

#### Scenario: Malformed re-scan data
- **WHEN** `rescan` is a string, has an unknown `state`, a `latest_document_id` that is not a UUID, or a `checked_at` that is not a timestamp
- **THEN** an unknown state shows no badge, and the invalid id or time is left out of the line instead of being shown
