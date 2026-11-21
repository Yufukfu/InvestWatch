# Follow-ups

| # | Finding | Source | Disposition |
|---|---|---|---|
| 1 | Postgres keeps its default capabilities. The official entrypoint starts as root, `chown`s the data directory and drops to the `postgres` user with `su-exec`, so it needs `CHOWN`, `DAC_OVERRIDE`, `FOWNER`, `SETUID` and `SETGID`. `cap_drop: [ALL]` plus `cap_add` of exactly those five is possible but untested here. | Kacper's review item 12 | `new-item`: Kacper's service; test on an empty volume first |
| 2 | Postgres and Caddy are pinned by tag, not digest. | Kacper's review item 12 (already `infra-compose` follow-up 9) | `new-item`: pin both digests with the next image bump |
| 3 | The `ollama` service needs `OLLAMA_CONTEXT_LENGTH=8192` for the stage-2 LLM change. The `/v1` endpoint cannot set `num_ctx` per request, so the default context can silently truncate a ~3k-token chunk plus the prompt. Add `OLLAMA_CONTEXT_LENGTH: ${OLLAMA_CONTEXT_LENGTH:-8192}` to `ollama` in `infra/compose.yaml`, an `OLLAMA_CONTEXT_LENGTH=8192` line in `.env.example`, and a sentence in `infra/README.md`. | Coordinator, for the stage-2 LLM change (arrived after this change was archived) | `new-item`: done in #32 (branch `chore/ollama-context-length`); config only, covered by the existing config probes |
