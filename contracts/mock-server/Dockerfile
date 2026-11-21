# Build from the contracts/ directory so the schemas and mocks are in the context:
#   docker build -f contracts/mock-server/Dockerfile -t iw-mock-server contracts
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 app
WORKDIR /app

COPY mock-server/requirements.txt mock-server/requirements.txt
RUN pip install -r mock-server/requirements.txt

COPY schemas contracts/schemas
COPY mocks/*.json contracts/mocks/
COPY openapi.yaml contracts/openapi.yaml
COPY mock-server/src mock-server/src

ENV PYTHONPATH=/app/mock-server/src \
    CONTRACTS_DIR=/app/contracts \
    MOCK_HOST=0.0.0.0 \
    MOCK_PORT=8000

USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"

CMD ["python", "-m", "iw_mock_server"]
