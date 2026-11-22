## ADDED Requirements

### Requirement: Module files merge in any order
`scraper/compose.yaml` SHALL resolve its includes the same way whichever directory is the project directory, so the documented `docker compose -f infra/compose.yaml -f api/compose.yaml -f scraper/compose.yaml` chain and the root `compose.yaml` yield the same scraper services.

#### Scenario: Documented chain
- **WHEN** `docker compose config` runs with `-f infra/compose.yaml -f api/compose.yaml -f scraper/compose.yaml`
- **THEN** it exits 0 and the model defines `worker`, `scheduler`, `seed` and `renderer`

#### Scenario: Root file
- **WHEN** `docker compose config` runs with the root `compose.yaml`
- **THEN** it exits 0 and the model defines the same four services
