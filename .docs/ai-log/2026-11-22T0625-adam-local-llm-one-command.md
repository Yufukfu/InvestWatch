---
when: Sun 06:25
who: Adam
---

## What was done with AI

A Claude Code agent audited the brief against the repo and found the open-model path needed hand-editing `.env`. It added `./scripts/init-env.sh --local-llm`, which writes the Ollama `LLM_*` and `EMBED_BASE_URL` lines and `COMPOSE_PROFILES=llm`, so a plain `docker compose up --build` starts Ollama and analytics uses it. It added four `infra/tests/smoke.sh env` checks (wiring through `docker compose config`, a custom `LOCAL_LLM_MODEL`, an existing file left alone, the default unchanged). It checked ollama.com for Gemma 4 tags. It started the stack from a fresh `.env` made by the flag: analytics logged `llm configured` and `embeddings configured` as `local`, and both models were pulled.

## Outcome / lesson

The gemma3:4b gold-set run and latency were not measured. On the 8 GB Docker VM shared with other agents' stacks, `llama-server` was SIGKILLed while loading the model (container peak 1.75 GiB, far below its 6 GiB limit, so the VM was out of memory), and the first embeddings call timed out at 15 s on a cold load. The infra README claim that both models fit the 6 GiB limit is therefore unverified on small machines. A first test used `docker compose config | grep -q` and failed only because `grep -q` closed the pipe on compose under `pipefail`; the output is captured first now.
