# Spec Delta

## Purpose
Persist a parsed document safely and announce it to analytics, so downstream consumers only ever see schema-valid, deduplicated documents that are already committed.

## ADDED Requirements

### Requirement: Author never comes from the parsed page
The scraper SHALL NOT copy `author` from a parsed page into a document, because page markup (`<meta>`, `rel=author`, embedded JSON) is controlled by the post's writer and analytics routes on `author.handle` and `author.profile_url`.

#### Scenario: Page supplies an author
- **WHEN** a parsed page carries an `author` with a firm's `profile_url`
- **THEN** the stored document has no `author`
