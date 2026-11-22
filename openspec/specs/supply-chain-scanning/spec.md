# supply-chain-scanning Specification

## Purpose

Automatic dependency and secret scanning of the repository in CI with open-source tools and no vendor account, so every pull request shows whether it adds a known vulnerability or a hard-coded secret (ADR 0209).

## Requirements

### Requirement: Scans run on every pull request and on demand
The repository SHALL run the security scans on every pull request to `main` and on a manual trigger. The result SHALL be visible on the pull request. The scans SHALL NOT be required checks, so a failing scan never blocks a merge by itself.

#### Scenario: Pull request opened
- **WHEN** a pull request to `main` is opened or updated
- **THEN** the secret scan and the dependency scans run, and each one reports pass or fail on the pull request

#### Scenario: Manual run
- **WHEN** a teammate starts the security workflow by hand on a branch
- **THEN** the same scans run on that branch

#### Scenario: Failing scan does not block
- **WHEN** a scan fails on a pull request
- **THEN** the pull request can still be merged, because no scan is a required check

### Requirement: Secret scan over the full history
The secret scan SHALL read the full git history of the checked-out ref and fail on any finding that the reviewed allowlist does not cover. Its output SHALL redact the matched values. Every allowlist entry SHALL name the file and the reason it is not a secret.

#### Scenario: Known false positives only
- **WHEN** the scan runs on `main`, whose only findings are the two allowlisted mock ids in `contracts/mocks/generate_mocks.py`
- **THEN** the scan passes

#### Scenario: New hard-coded secret
- **WHEN** a commit adds a credential-shaped value outside the allowlist
- **THEN** the scan fails and its log shows the rule, file and line, but not the value

#### Scenario: History not readable
- **WHEN** the checkout is shallow and has only the last commit
- **THEN** the workflow fetches the full history before scanning, so the scan never reports a clean result over a single commit

### Requirement: Dependency scans over every manifest
The dependency scans SHALL cover every `package-lock.json` and every `requirements*.txt` in the repository. Every finding SHALL fail the OSV-Scanner and `pip-audit` scans. The npm audit step SHALL fail on npm advisories of high or critical severity and SHALL report lower ones without failing. Per ADR 0209 decision 2, only package names and versions leave the runner.

#### Scenario: Vulnerable pin
- **WHEN** a manifest pins a version with a known OSV advisory
- **THEN** the repository-wide scan fails and names the package, the version and the advisory id

#### Scenario: New manifest
- **WHEN** a pull request adds a new `requirements.txt` or `package-lock.json`
- **THEN** the repository-wide scan includes it without a workflow edit

#### Scenario: npm moderate advisory
- **WHEN** `web/` has only moderate or low npm advisories
- **THEN** the npm audit step passes and still prints them

### Requirement: Offline on-premise scan on demand
The workflow SHALL offer a dependency scan that first downloads the vulnerability database and then scans with no further network access for the scan itself. It SHALL run when started by hand with the offline option, and on a pull request that changes the security workflow itself. Other pull requests SHALL NOT run it.

#### Scenario: Offline run requested
- **WHEN** a teammate starts the workflow by hand with the offline option
- **THEN** the offline scan downloads the database, scans every manifest against it, and reports pass or fail

#### Scenario: Pull request that does not change the security workflow
- **WHEN** a pull request that leaves the security workflow file unchanged triggers the workflow
- **THEN** the offline scan is skipped

#### Scenario: Pull request that changes the security workflow
- **WHEN** a pull request changes the security workflow file, for example to bump a scanner pin
- **THEN** the offline scan runs on that pull request, so the change is proven before the merge

### Requirement: Pinned scanning tools
Every action the security workflow uses SHALL be pinned to a full commit SHA. Every container image it runs SHALL be pinned by digest, and every scanner installed from a package index SHALL be pinned to an exact version. A repository test SHALL fail when any of these is unpinned.

#### Scenario: Unpinned action
- **WHEN** the workflow names an action by tag only, for example `actions/checkout@v4`
- **THEN** the pin test fails and names the line

#### Scenario: Image without digest
- **WHEN** the workflow runs a container image without an `@sha256:` digest
- **THEN** the pin test fails and names the image

#### Scenario: Unpinned scanner package
- **WHEN** the workflow installs `pip-audit` without an exact `==` version
- **THEN** the pin test fails
