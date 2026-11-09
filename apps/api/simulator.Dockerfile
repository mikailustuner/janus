# syntax=docker/dockerfile:1
# Janus simulator worker (simulation-service design §8). Build context: repository root.
#   docker build -f apps/api/simulator.Dockerfile -t janus-simulator:<commit> .
# R 4.6.1 with CRAN pinned to a dated Posit Package Manager snapshot (2026-10-28) by the rocker
# image; httk pinned below and checked at build time. Multi-arch base (linux/amd64, linux/arm64):
# on an arm64 host the packages compile from source if no binary exists.
FROM rocker/r-ver:4.6.1@sha256:780bc87219250a6dfffef6c812999731986fd94d8d5f7e572d1157c923d1b4bb

ARG HTTK_VERSION=2.7.4
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3.12 python3.12-venv \
    && rm -rf /var/lib/apt/lists/*
RUN install2.r --error --skipinstalled --ncpus -1 httk \
    && Rscript -e "stopifnot(as.character(packageVersion('httk')) == '${HTTK_VERSION}')" \
    && rm -rf /tmp/downloaded_packages

COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.12 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/.python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY apps/api/janus ./janus
# The allow-list and the cited parameters; nothing else from data/ is needed.
COPY data/simulation ./data/simulation
COPY data/time_machine/compartmental_pk.csv ./data/time_machine/compartmental_pk.csv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

RUN useradd --system --uid 10002 --no-create-home simulator
USER simulator
ENV PATH="/app/.venv/bin:$PATH" \
    HOME=/tmp \
    TMPDIR=/tmp

CMD ["python", "-m", "janus.simulation.worker"]
