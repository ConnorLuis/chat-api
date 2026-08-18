# syntax=docker/dockerfile:1

ARG PYTHON_IMAGE=python:3.10.19-slim-bookworm
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# Install the production runtime plus the advertised OpenAI and LangChain
# integrations. Real Hugging Face embeddings remain an opt-in custom-image
# extension because sentence-transformers is intentionally not in the base
# runtime image.
COPY constraints.txt \
     requirements.txt \
     requirements-langchain.txt \
     requirements-openai.txt \
     ./

RUN python -m pip install \
      -r requirements.txt \
      -r requirements-langchain.txt \
      -r requirements-openai.txt \
    && python -m pip check

RUN groupadd --gid 10001 app \
    && useradd \
      --uid 10001 \
      --gid app \
      --create-home \
      --home-dir /home/app \
      app \
    && mkdir -p \
      /app/data \
      /app/runs \
      /app/kb/chroma \
      /app/kb/docs \
      /app/scripts \
    && chown -R app:app /app /home/app

COPY --chown=app:app src ./src
COPY --chown=app:app config ./config
COPY --chown=app:app prompts ./prompts
COPY --chown=app:app scripts/docker-entrypoint.sh ./scripts/

RUN chmod 0555 /app/scripts/docker-entrypoint.sh

USER app

EXPOSE 8000

# Readiness covers both the HTTP process and the configured database. The
# standard library probe avoids adding curl only for the health check.
HEALTHCHECK \
  --interval=10s \
  --timeout=3s \
  --start-period=15s \
  --retries=5 \
  CMD ["python", "-c", "import json, urllib.request; response = urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2); payload = json.load(response); raise SystemExit(0 if response.status == 200 and payload.get('status') == 'ready' else 1)"]

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]

CMD ["python", "-m", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
