# Follow-ups

## Manual run with real `bge-m3` (task 4.3, 2026-11-22)

`docker compose -p iw-embgate --profile llm up` could not start. Docker refused a new network ("all predefined address pools have been fully subnetted"), because the iw-demo, iw-int2 and iw-int3 stacks already use them, and those stacks were not touched. The run therefore used the CLI (`python -m investwatch_analytics.cli … --no-llm`) against a standalone Ollama container (the same image digest as `infra/compose.yaml`) serving `bge-m3` on CPU. The host CPU was at about 88% from other sessions.

| What | Result |
|---|---|
| Latency, seeds (24 calls, first build) | 0.5-6 s each, about 40 s in total on a loaded host. Under heavier load an earlier run took 0.2-14 s per call. A quiet host does all 24 in one batched request in 2.5 s. The build runs between messages, and afterwards the seed vectors come from the Redis cache |
| Latency, documents | 0.6-3.3 s per call warm. Under load, three calls hit `EMBED_TIMEOUT_S` (15 s), the breaker opened, and the findings became `model.embedder = null` with the gate dictionary-only, as designed |
| Mock documents (`contracts/mocks/documents.json`, 8) | none dropped. 3 `firm_own` bypass; 5 pass on the dictionary (2-7 hits). Findings are identical with and without the gate (3 M3 findings, `model.embedder: bge-m3`) |
| Demo sources (fetched once each with the scraper's `parsing._text`) | xtb.com/pl/ike: `firm_own` bypass (M2 0.5). icobench: dictionary, 494 hits (M1 0.818). moneteo ranking: dictionary, 287 (M1 0.378). moneteo XTB review: dictionary, 320 (M1 0.378, M3 0.5). tradingview.com: dictionary, 160 (`not_targeting_poland`). EY family office: dictionary, 53 (`no_signals`). KNF warnings: dictionary, 1026 (`official_source`). ppcg.com.pl: dictionary, 312 (M1 0.622, M3 0.622). comparic.pl answered 403 to a plain fetch (the scraper uses a browser TLS profile), so it was not checked. Every demo page passes on the dictionary, so the embedding rescue cannot change any demo decision |

During the demo-page run the embedder was timing out and the Docker engine then went down (the C: drive filled up at about 04:20). The demo-page decisions above are therefore dictionary-only. They need no embedding, since none of the pages is a dictionary drop.

## Real stack run (`docker compose -p iw-embgate --profile llm`, 2026-11-22 04:20-04:55)

The coordinator freed Docker networks by stopping finished test stacks (with Damian's OK), and the stack then came up: postgres, redis, minio, api, ollama, analytics, scraper worker and scheduler. `ollama-pull` failed on a bug in `infra/compose.yaml`, filed as issue #149: `OLLAMA_MODELS` is also Ollama's models-directory variable. `bge-m3` was copied into the stack's volume by hand.

- **Worker wiring (F2) works.** At start the worker logged `embedding gate degraded` (`embed_unavailable`, model missing). Between messages, after one cooldown, it logged `embedding gate restored` with 4 classes. The first call (cold) took 13.8 s; warm calls took 0.2-3.6 s.
- **Scan burst.** One scan request per seeded source (19) gave 223 documents. Three 4000-character embeddings took more than 15 s on the loaded CPU (a test suite was running beside it), the breaker opened, and the burst finished inside the 60 s cooldown. `iw:stats:gate`: passed 160, dropped 58 (56 `dictionary_only_fallback`, 2 short `dictionary`), bypassed 5, so the rescue did not run during the burst. Nothing failed.
- **The 56 fallback drops, re-queued on a quiet CPU** (`XADD iw:documents`, own stack only). All 56 took the `embedding` path: **34 rescued, 22 dropped**; p50 2.8 s, max 12.8 s per call. All are Telegram posts without any dictionary term.
  - **Rescued:** about 31 are trading posts ("Podejmuje tutaj próbę z longiem", "ustawiam sobie limit order na longa", "UPDATE RYNKOWY", Fed rate decisions). Two are off-topic stream chatter ("gramy w GTA", "Odpalamy transmisję"). One is a borderline "dołączenie ZA DARMO".
  - **Dropped:** mostly bare "Zapraszam na live" links and Iran news. Three are trading posts missed at margins −0.018, +0.012 and +0.030.
  - **No findings.** The rescued posts produced none (no M3 offer signal), so the false rescues cost CPU only.
  - **The +0.030 miss was a rounding mismatch.** The raw margin was below 0.03, while 0.03 was logged. Fixed in b47e9102: the decision now uses the logged 3-place margin.
- Rough precision of the rescue on this real sample is about 0.91-0.94 (31-32 of 34). This is the author's reading of the posts, not a labelled set.

## Items

| # | Source | Item | Disposition |
|---|---|---|---|
| F1 | manual run | The centroids are built with one embedding call per seed (24 calls, tens of seconds on a loaded CPU at the first start). A batched `input` list would do it in one call (about 2.5 s measured) | `new-item`: needs an `embed_many` on `EmbedClient`; the start-up cost is paid once, then the seeds are cached |
| F2 | review groups 2-3 | The two wiring lines in `worker.main` (`with_embedding`, the shared embedder) have no unit test | `docs`: checked in the real stack run (`embedding gate restored`, `path_embedding` 56, `rescued` 34) |
| F3 | review groups 2-3 | Against a slow but working embedder, `warm()` can delay reading the next message by up to `EMBED_TIMEOUT_S` once per cooldown. It holds no message, so nothing is reclaimed | `wont-fix`: bounded (one failed seed stops the attempt), outside the claim-idle window |
| F4 | design §4 | The check set is small and synthetic. The margin 0.03 sits about 0.01 from the nearest error on each side | `docs`: re-run `eval/gate_calibrate.py` after a model or seed change, and add real no-hit posts when available |
| F5 | review group 1 | While the embedder is down, `warm` and `rescue` could log alternating reasons | `fix-here` (e8fa4722): `rescue` no longer logs `no_centroids` |
| F6 | real stack run | In a scan burst on a loaded CPU, three slow 4000-character embeddings open the breaker, and the gate is dictionary-only for the 60 s cooldown (56 no-hit posts not rescued) | `new-item`: a shorter input for the gate embedding, or re-queueing the `dictionary_only_fallback` drops once the breaker closes |
| F7 | real stack run | The margin was compared unrounded but logged rounded, so a drop could show `margin` equal to the threshold | `fix-here` (b47e9102) |
| F8 | real stack run | `ollama-pull` cannot pull any model (`OLLAMA_MODELS` clash) | `new-item`: issue #149, infra |
