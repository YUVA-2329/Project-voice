# PROJECT VOICE — API image (FastAPI + uvicorn). No speech models: see Dockerfile.worker.
#
# Multi-stage: dependencies are resolved in a builder stage into a self-contained virtualenv
# which is copied into a slim runtime stage that has no compiler toolchain.
# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.11.10-slim-bookworm

# ------------------------------------------------------------------------------ builder
FROM ${PYTHON_IMAGE} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv "$VIRTUAL_ENV" \
    && pip install --upgrade pip wheel

WORKDIR /src
COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
# `realtime` adds sherpa-onnx (ONNX Runtime only, no torch) so Conversation mode's server-side
# VAD + Whisper can run inside the API. Build with --build-arg API_EXTRAS="" to leave it out.
ARG API_EXTRAS=realtime
RUN if [ -n "$API_EXTRAS" ]; then pip install ".[${API_EXTRAS}]"; else pip install .; fi

# ------------------------------------------------------------------------------ runtime
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# ffprobe validates uploads; libsndfile backs `soundfile` (conversation PCM decoding); curl → healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 curl tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home /app --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app pyproject.toml README.md alembic.ini ./
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app docker/entrypoint-api.sh /usr/local/bin/entrypoint-api.sh
RUN chmod 0755 /usr/local/bin/entrypoint-api.sh \
    && mkdir -p /data/storage /data/tmp /models \
    && chown -R app:app /app /data /models

ENV PV_STORAGE_LOCAL_DIR=/data/storage \
    PV_TMP_DIR=/data/tmp \
    PV_MODELS_DIR=/models

USER app
EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/system/health || exit 1

# The entrypoint waits for PostgreSQL, runs `alembic upgrade head` (PV_SKIP_MIGRATIONS=1 to
# disable) and then execs uvicorn behind tini so signals reach the server.
ENTRYPOINT ["tini", "--", "/usr/local/bin/entrypoint-api.sh"]
CMD []
