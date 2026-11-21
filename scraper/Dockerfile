# Build context is the repository root: docker build -f scraper/Dockerfile .
# (the image needs contracts/ for schema validation)
FROM python:3.12-slim-bookworm AS base

ARG TLS_CLIENT_VERSION=1.18.1
# sha256 of the upstream release assets (bogdanfinn/tls-client v1.18.1)
ARG TLS_SHA256_AMD64=719ad7f9772d4a72572e4eb9c1aace289a13eaa9bf3862c32f5dce6222d5644f
ARG TLS_SHA256_ARM64=9ee40f45a5336142948cc8c6a5a2f7805aaf95a975348e3faef104c90d8c5c15
ARG TARGETARCH

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY scraper/requirements.txt scraper/requirements.txt
RUN pip install -r scraper/requirements.txt

# noble-tls would fetch the *latest* tls-client through api.github.com at run time (unpinned, rate limited).
# Instead: download the pinned release asset by tag, verify its sha256, save it under the name noble-tls
# expects for this platform and write the .version file. A failed download or checksum fails the build.
RUN set -eu; \
    case "${TARGETARCH:-amd64}" in \
      amd64) UPSTREAM="tls-client-linux-ubuntu-amd64-${TLS_CLIENT_VERSION}.so"; SHA="${TLS_SHA256_AMD64}" ;; \
      arm64) UPSTREAM="tls-client-linux-arm64-${TLS_CLIENT_VERSION}.so"; SHA="${TLS_SHA256_ARM64}" ;; \
      *) echo "unsupported arch ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    DEPS="$(python -c 'import noble_tls, os; print(os.path.join(os.path.dirname(noble_tls.__file__), "dependencies"))')"; \
    EXPECTED="$(python -c "from noble_tls.utils.asset import generate_asset_name; print(generate_asset_name(version='${TLS_CLIENT_VERSION}'))")"; \
    mkdir -p "$DEPS"; \
    curl --proto '=https' --tlsv1.2 -fsSL -o "$DEPS/$EXPECTED" "https://github.com/bogdanfinn/tls-client/releases/download/v${TLS_CLIENT_VERSION}/${UPSTREAM}"; \
    echo "${SHA}  $DEPS/$EXPECTED" | sha256sum -c -; \
    printf '%s %s' "$EXPECTED" "${TLS_CLIENT_VERSION}" > "$DEPS/.version"; \
    python -c "import noble_tls; from noble_tls import Session, Client; Session(client=Client.CHROME_146_PSK); print('tls-client loaded')"

COPY contracts/ contracts/
COPY scraper/ scraper/
ENV PYTHONPATH=/app/scraper/src CONTRACTS_DIR=/app/contracts

FROM base AS test
RUN pip install -r scraper/requirements-dev.txt
WORKDIR /app/scraper
CMD ["pytest", "-q"]

# The renderer is its own image (ADR 0105): the browser runs hostile page code, so it never shares an image
# with the scraper's credentials. Build: docker build -f scraper/Dockerfile --target renderer-test .
FROM python:3.12-slim-bookworm AS renderer-base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw
WORKDIR /app
COPY scraper/requirements-renderer.txt scraper/requirements-renderer.txt
# the headless shell is all a screenshot needs; the browser build is fixed by the playwright pin
RUN pip install -r scraper/requirements-renderer.txt \
 && playwright install --with-deps --only-shell chromium \
 && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY scraper/src/iw_renderer scraper/src/iw_renderer
# the modules shared with the scraper: address checks and block markers, free of the fetch client (no noble-tls here)
COPY scraper/src/iw_scraper/__init__.py scraper/src/iw_scraper/addresses.py scraper/src/iw_scraper/blocking.py scraper/src/iw_scraper/
ENV PYTHONPATH=/app/scraper/src

FROM renderer-base AS renderer-test
COPY scraper/requirements-renderer-dev.txt scraper/requirements-renderer-dev.txt
RUN pip install -r scraper/requirements-renderer-dev.txt
COPY scraper/pyproject.toml scraper/pyproject.toml
COPY scraper/tests_renderer scraper/tests_renderer
WORKDIR /app/scraper
CMD ["pytest", "-q", "tests_renderer"]

FROM base AS runtime
# code and the tls-client library stay root-owned and read-only for the runtime user
RUN useradd --system --uid 10001 iw
USER iw
WORKDIR /app/scraper
CMD ["python", "-m", "iw_scraper"]
