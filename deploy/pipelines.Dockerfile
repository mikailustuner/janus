# syntax=docker/dockerfile:1
# Janus pipelines, for jobs that must run on the server (the TİTCK list: "fetch at runtime",
# data-sources.md). Build context: pipelines/. Base images are multi-arch.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY janus_pipelines ./janus_pipelines
COPY sources.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
RUN useradd --system --uid 10002 --no-create-home pipelines
USER pipelines
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["janus-pipelines"]
