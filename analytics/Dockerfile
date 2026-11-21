# analytics/ deployment unit: the iw:documents stream worker. Self-contained build context (analytics-plan §12.1):
#   docker build -t investwatch/analytics analytics
# Config is env only (analytics/.env.example). Rules-only for now: no LLM call, model.llm = null.
FROM public.ecr.aws/docker/library/python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 app
WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# The registry seed sits next to src/ so config._DEFAULT_REGISTRY (src/../registry/seed.csv) resolves;
# the rule catalogue YAML ships inside the package.
COPY registry registry
COPY src src

ENV PYTHONPATH=/app/src \
    HEALTH_PORT=8001

USER 10001
EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('HEALTH_PORT', '8001') + '/health', timeout=2)"]
CMD ["python", "-m", "investwatch_analytics.worker"]
