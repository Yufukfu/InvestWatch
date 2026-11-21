# Follow-ups

Review findings and declined-to-judge items that are not fixed in the group that raised them.

| Source | Item | Disposition |
|---|---|---|
| group 2 review | `response.body()` reads the whole main document in Python before the block check; the 8 MB cap covers the PNG only | wont-fix: `block_marker` ignores bodies over 20 kB and Chromium already holds the document in its own process, so the copy adds no new exposure; the container memory limit (task 3.2) bounds both. Revisit if 3.2's limits test shows pressure |
| group 2 review | `renderer-base` has no `USER`, and the runtime target does not exist yet | fix-here: task 3.2 (runtime target, non-root) |
| group 2 review | whether the renderer container can reach compose-internal services | fix-here: task 3.2 (networks `egress` and `render` only, checked with `docker inspect`) |
| group 2 review | production launch flags | fix-here: `LAUNCH_ARGS` in `confine.py` (sandbox, WebRTC UDP policy, no QUIC); task 3.1's launcher must use it |
