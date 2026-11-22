## MODIFIED Requirements

### Requirement: Audited supply chain
The scraper's pinned dependencies SHALL be scanned with `pip-audit` and the result reported in the PR body's "Security scans" section (ADR 0209, decision 2), while `.docs/security-audit.md` keeps a scraper container section with the container's credentials, networks and hardening.

#### Scenario: Audit recorded
- **WHEN** the change is ready for review
- **THEN** the PR body's "Security scans" section has the `pip-audit` command for `scraper/requirements*.txt`, its version and its result with no unresolved finding, and `.docs/security-audit.md` has a scraper container section whose claims match `scraper/compose.yaml`
