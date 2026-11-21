# Follow-ups

Review findings and declined-to-judge items that are not fixed in the group that raised them.

| Source | Item | Disposition |
|---|---|---|
| group 2 review | `response.body()` reads the whole main document in Python before the block check; the 8 MB cap covers the PNG only | wont-fix: `block_marker` ignores bodies over 20 kB and Chromium already holds the document in its own process, so the copy adds no new exposure; the container memory limit (task 3.2) bounds both. Revisit if 3.2's limits test shows pressure |
| group 2 review | `renderer-base` has no `USER`, and the runtime target does not exist yet | fix-here: task 3.2 (runtime target, non-root) |
| group 2 review | whether the renderer container can reach compose-internal services | fix-here: task 3.2 (networks `egress` and `render` only, checked with `docker inspect`) |
| group 2 review | production launch flags | fix-here: `LAUNCH_ARGS` in `confine.py` (sandbox, WebRTC UDP policy, no QUIC); task 3.1's launcher must use it |
| group 3 | the worker must join the `render` network and read `RENDERER_URL`; `scraper/compose.yaml` exists only in PR #52 | fix-here: done in the merge of origin/main: `scraper/compose.yaml` includes `compose.renderer.yaml` and the worker joins `render` (ADR 0106); no root include line |
| group 3 | root `compose.yaml` is Kacper's file; one include line added | docs: tell Kacper in the PR body |
| issues session | parked branch `scraper/scraper-render` (worktree `scraper-render`) holds a parallel in-image Chromium with a DevTools Fetch check on redirect hops, a 10 MiB screenshot cap, NUL and lone-surrogate cleanup; its ADR is also numbered 0105 | fix-here: compare the redirect-hop check with the after-load check of this change; adopt the surrogate cleanup in group 5; nothing else is taken (that branch is parked, not pushed) |
| group 4 | the queue's real domain pause is `DomainHealth` (`iw:domain:<host>:paused`); `DomainGate` (`iw:dom:`) is read by nothing but the render step, so a `Retry-After` from a render block holds back later renders, not fetches | new-item: decide with the orchestration owner whether the queue should consult `DomainGate`; this change checks both pauses and writes the gate |
| group 3 review | `docker stop` exit code, `init`, `pids_limit`, `source_host` hostname check | fix-here: done in `da4f8c6`; `ports` stays caller-supplied because the scraper is the only caller on the private `render` network |
