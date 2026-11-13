# syntax=docker/dockerfile:1
# Janus API. Build context: repository root (the API reads the committed data/ and datasets/).
# Base images are multi-arch (linux/amd64, linux/arm64).
FROM python:3.15-slim AS base

# Security fixes released after the base image was built (deploy C3: image scan in CI).
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, for layer caching.
COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/.python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY apps/api/janus ./janus
COPY apps/api/alembic.ini ./
COPY apps/api/migrations ./migrations
# Committed reference data read at run time (resolution tables, séance package, evidence papers).
COPY data ./data
COPY datasets ./datasets
# Source registry (licences, cadences) read by the data loaders (resolution, integrity).
COPY pipelines/sources.toml ./pipelines/sources.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

RUN useradd --system --uid 10001 --no-create-home janus
USER janus

ENV PATH="/app/.venv/bin:$PATH"
# Deployed git commit, shown at /health (deploy DP10). Empty for local builds.
ARG JANUS_COMMIT=""
ENV JANUS_COMMIT=$JANUS_COMMIT
EXPOSE 8000

# Access logs are off: URLs of medical endpoints may carry product codes (privacy.md).
CMD ["uvicorn", "janus.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
