# 0306. Object storage and Redis images

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written for Damian; accepted by: pending approval of the `infra-compose` PR

## Context

The integration plan puts raw HTML, screenshots and media in a MinIO bucket `iw-raw` ([integration-plan.md](../integration-plan.md) §1-§2). The contracts and mocks name it (`contracts/schemas/scraped-document.schema.json`, `contracts/mocks/health.json`), and `scraper-v1` writes to it. Redis carries `iw:documents`, `iw:events` and `iw:settings:thresholds` ([0305](0305-threshold-storage.md)). The UKNF task requires an open-source, on-premise stack, and the jury reviews the libraries used ([0304](0304-llm-serving.md) context). [0202](0202-deployment-topology.md) takes images from `public.ecr.aws` mirrors because Docker Hub rate-limits anonymous pulls. The `infra-compose` change (`openspec/changes/infra-compose/`) adds both services.

Evidence, checked on 2026-11-21 with `docker manifest inspect` (registry metadata only, nothing pulled), Docker 28.5.1:

| Image | Result |
|---|---|
| `docker.io/minio/minio:latest` | denied: authentication required |
| `quay.io/minio/minio:latest`, `:RELEASE.2025-09-07T16-13-09Z` | no such manifest |
| `cgr.dev/chainguard/minio:latest` | available |
| `cgr.dev/chainguard/minio-client:latest` | available |
| `docker.io/chrislusf/seaweedfs:latest` | HTTP 429, anonymous pull rate limit |
| `public.ecr.aws/docker/library/redis:8-alpine` | available |
| `public.ecr.aws/docker/library/valkey:8-alpine` | no such manifest |

Public sources agree: MinIO stopped publishing community-edition binaries and images in October 2025, and its GitHub README says the community edition is distributed as source only ([github.com/minio/minio](https://github.com/minio/minio)). Chainguard publishes free MinIO images built from that source, with only the `latest` tag free ([Chainguard blog](https://www.chainguard.dev/unchained/secure-and-free-minio-chainguard-containers)). Redis 8 is offered under a choice of RSALv2, SSPLv1 or AGPLv3, and AGPLv3 is OSI-approved ([redis.io licences](https://redis.io/legal/licenses/)). Redis 7.4 has only the source-available licences.

## Options considered

Object storage:

1. **Last upstream MinIO image.** It cannot be pulled (table above), so it is not an option.
2. **Chainguard's MinIO build (`cgr.dev/chainguard/minio`), pinned by digest.** The image ships `sh`, `bash` and `mc` (checked by running it), so the init step needs no second image. `cgr.dev/chainguard/minio-client` has no shell and cannot run an init script. AGPLv3 MinIO, unchanged API, and nothing in the docs or contracts changes. The free tier exposes only `latest`, so the build must be pinned by digest, and a digest may be removed later. Upstream is archived, so fixes depend on Chainguard rebuilding.
3. **SeaweedFS (Apache-2.0, S3 gateway).** A maintained project. It is a different server with different configuration and policy commands, the docs and the mocks' `minio` health key would need renaming or would mislead, and the only image tried is on Docker Hub, which returned 429.
4. **Build MinIO from source in our own Dockerfile.** Full control, but a Go build of an archived project adds time to every fresh clone and still gets no upstream fixes.

Redis:

1. **Redis 8 (`redis:8-alpine`) from the ECR mirror.** OSI-approved licence option, the same name every doc uses, and available on the mirror.
2. **Valkey 8 (BSD).** Wire-compatible, but not on the mirror at the tag tried, so it would come from Docker Hub.
3. **Redis 7.4.** Source-available only, which conflicts with the open-source requirement.

## Decision

Object storage: option 2. The service keeps the name `minio` and the `MINIO_*` variables. It runs `cgr.dev/chainguard/minio`, and the one-shot `minio-init` uses the same image (its `mc`), pinned by the digest below. Redis: option 1, `public.ecr.aws/docker/library/redis:8-alpine`, pinned by digest.

Rationale, from the evidence above:
- Option 2 is the only MinIO image that can be pulled at all, and it changes nothing in the contracts, mocks, `scraper-v1` or the integration plan four hours before Integration #1.
- Clients use the S3 API through the `minio` client library, so moving to SeaweedFS later changes the image and the init script, not module code.
- Redis 8 is the only Redis-compatible image tried that is both available on the ECR mirror (0202's pull policy) and under an OSI-approved licence.

Digests, pulled 2026-11-21:
- `minio`: `cgr.dev/chainguard/minio@sha256:e9cf6b99c226e9539ed0f14b6f00e37b07da153c7ba1f4f8709c807574b471ec`, which reports `RELEASE.2026-11-16T00-11-40Z`, go1.27.4.
- `redis`: `public.ecr.aws/docker/library/redis:8-alpine@sha256:7958cfbb9d152f87dadfbc89f1b0b15938f0b81ff8982feb327476f4911935c3`, Redis 8.10.3.

## Consequences

- No doc, contract or mock renames. The hand-in README names both AGPLv3 components, run unmodified as separate services.
- A pinned Chainguard digest that disappears is a one-line bump to the new `latest` digest. If Chainguard stops publishing, the fallback is option 3 (SeaweedFS).
- Object storage gets no upstream security fixes. Exposure is limited: the internal `data` network only, no host port (except the loopback dev override), bucket-scoped app credentials. Revisit after the hackathon.
- Redis must keep `appendonly yes` for 0305, and `noeviction` so stream entries are never dropped (see `infra-compose` design).
