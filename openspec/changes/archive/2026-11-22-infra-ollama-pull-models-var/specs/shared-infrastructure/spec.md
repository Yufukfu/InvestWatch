## MODIFIED Requirements

### Requirement: Optional local LLM behind a profile
The stack SHALL define an `ollama` service and a one-shot `ollama-pull` that pulls every model in `OLLAMA_PULL_MODELS` (default `gemma3:4b bge-m3`), both only in the compose profile `llm`. Without the profile, neither SHALL start and no model weights SHALL be downloaded. With the profile, `ollama` SHALL serve the OpenAI-compatible API under `/v1` to containers on `data` at `http://ollama:11434/v1`, and keep the weights in a named volume.

#### Scenario: Plain up downloads no weights
- **WHEN** `docker compose up -d` runs without `--profile llm`
- **THEN** `docker compose ps -a` lists neither `ollama` nor `ollama-pull`, and no `ollama` volume exists

#### Scenario: Profile serves gemma3:4b and bge-m3
- **WHEN** `docker compose --profile llm up -d` has finished and `ollama-pull` has exited 0
- **THEN** `GET http://ollama:11434/v1/models` from a container on `data` lists `gemma3:4b` and `bge-m3`

#### Scenario: Pull fails without network
- **WHEN** the `llm` profile starts and the model registry cannot be reached
- **THEN** `ollama-pull` exits non-zero, and every service outside the profile stays healthy

#### Scenario: Only the pull reaches the internet
- **WHEN** the `llm` profile runs
- **THEN** of `ollama` and `ollama-pull`, only the `ollama-pull` one-shot SHALL reach the internet
- **AND** `ollama` SHALL publish no host port and SHALL NOT join a network with internet access

#### Scenario: Default pull list is pulled
- **WHEN** `docker compose --profile llm up --exit-code-from ollama-pull ollama-pull` runs with `OLLAMA_PULL_MODELS` unset and the registry reachable
- **THEN** it exits 0 and the model volume holds `gemma3:4b` and `bge-m3`
- **AND** `ollama-pull` SHALL NOT set `OLLAMA_MODELS`, which Ollama reads as its model directory
