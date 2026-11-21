# Follow-ups

Out-of-scope findings from the per-group reviews (iw-commit-cycle step 8).

| # | Finding | Source | Disposition |
|---|---|---|---|
| 1 | `edge` is a normal bridge, so every routed service (gateway, web, later api) has outbound internet. Making it internal needs a separate publishing network for the gateway only. | group 5 review | `new-item`: Kacper's gateway topology (ADR 0202); spec and design now state the real rule |
| 2 | On Linux Docker before 28.0, ports published on `127.0.0.1` can be reached from the LAN by routing to the container IP; the dev-ports override relies on loopback binding. | group 5 review | `docs`: dev ports are for laptops on Docker 28+ (verified on 28.5.1) |
| 3 | `s3:AbortMultipartUpload` / `ListMultipartUploadParts` may be needed if a client uploads large media in parts. | group 4 review | `new-item`: add to the `iw-bucket-rw` policy when the scraper stores media |
| 4 | Smoke helpers pass throwaway MinIO test credentials on the host's `docker run` argv (`-e MC_HOST_t=...`). | group 4 review | `wont-fix`: test-only, random per run, removed with the project |
