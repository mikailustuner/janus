# syntax=docker/dockerfile:1
# Janus API. Base images are multi-arch (linux/amd64, linux/arm64).
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, for layer caching.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY janus ./janus
COPY alembic.ini ./
COPY migrations ./migrations
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

RUN useradd --system --uid 10001 --no-create-home janus
USER janus

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# Access logs are off: URLs of medical endpoints may carry product codes (privacy.md).
CMD ["uvicorn", "janus.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
