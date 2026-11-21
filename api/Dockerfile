# Build from the repository root so contracts/ is in the context (the API validates events against it):
#   docker build -f api/Dockerfile -t investwatch/api .
# The same image runs the one-shot migration (alembic upgrade head, the default CMD) and the API (python -m investwatch_api).
FROM public.ecr.aws/docker/library/python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 app
WORKDIR /app

COPY api/requirements.txt api/requirements.txt
RUN pip install -r api/requirements.txt

COPY contracts/schemas contracts/schemas
COPY contracts/openapi.yaml contracts/openapi.yaml
COPY api/alembic.ini api/alembic.ini
COPY api/migrations api/migrations
COPY api/src api/src

ENV PYTHONPATH=/app/api/src \
    CONTRACTS_DIR=/app/contracts

USER app
WORKDIR /app/api
CMD ["alembic", "upgrade", "head"]
