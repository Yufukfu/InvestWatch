# Follow-ups

| # | Finding | Source | Disposition |
|---|---|---|---|
| 1 | Postgres keeps its default capabilities. The official entrypoint starts as root, `chown`s the data directory and drops to the `postgres` user with `su-exec`, so it needs `CHOWN`, `DAC_OVERRIDE`, `FOWNER`, `SETUID` and `SETGID`. `cap_drop: [ALL]` plus `cap_add` of exactly those five is possible but untested here. | Kacper's review item 12 | `new-item`: Kacper's service; test on an empty volume first |
| 2 | Postgres and Caddy are pinned by tag, not digest. | Kacper's review item 12 (already `infra-compose` follow-up 9) | `new-item`: pin both digests with the next image bump |
