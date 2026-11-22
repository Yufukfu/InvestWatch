# Build context is api/. The contracts the API validates against come in as the named context `contracts`,
# the only input from outside this folder. From the repository root:
#   docker build --build-context contracts=contracts -t investwatch/api api
# The same image runs the one-shot migration (alembic upgrade head, the default CMD) and the API (python -m investwatch_api).
FROM public.ecr.aws/docker/library/python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 app
WORKDIR /app

COPY requirements.txt api/requirements.txt
RUN pip install -r api/requirements.txt

COPY --from=contracts schemas contracts/schemas
COPY --from=contracts openapi.yaml contracts/openapi.yaml
COPY alembic.ini api/alembic.ini
COPY migrations api/migrations
COPY src api/src

ENV PYTHONPATH=/app/api/src \
    CONTRACTS_DIR=/app/contracts

USER app
WORKDIR /app/api
CMD ["alembic", "upgrade", "head"]
