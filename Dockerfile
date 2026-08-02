# syntax=docker/dockerfile:1.7
# ==============================================================================
# Project Atlas — multi-stage image for the atlas-core service.
#
# builder : resolves dependencies into a self-contained virtual environment.
# runtime : slim, non-root, carries only the venv and the application source.
#
# Dependency resolution is a separate layer from source, so editing code does
# not invalidate the dependency cache.
# ==============================================================================

ARG PYTHON_VERSION=3.12

# Must match POETRY_VERSION in .github/workflows/ci.yml. poetry.lock records the
# version that generated it; a builder on an older Poetry can reject the lock.
ARG POETRY_VERSION=2.4.1

# ------------------------------------------------------------------------------
# Stage 1 — builder
# ------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ARG POETRY_VERSION

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=true \
    POETRY_VIRTUALENVS_IN_PROJECT=true

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# Dependency layer: manifests only. Rebuilt only when they change.
COPY pyproject.toml poetry.lock README.md LICENSE ./
RUN poetry install --only main --no-root

# Source layer, then link the workspace packages into the venv.
COPY packages/ ./packages/
COPY apps/ ./apps/
RUN poetry install --only main

# ------------------------------------------------------------------------------
# Stage 2 — runtime
# ------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/app/.venv/bin:${PATH}" \
    ATLAS_CONFIG_DIR=/app/config \
    ATLAS_ENV=production

# Least privilege: the service never needs to write outside /app/data.
RUN groupadd --system --gid 1000 atlas \
    && useradd --system --uid 1000 --gid atlas --home-dir /app --shell /usr/sbin/nologin atlas

WORKDIR /app

# The editable install records absolute paths under /app, so the source tree
# must land at the same location it occupied in the builder.
COPY --from=builder --chown=atlas:atlas /app/.venv/ ./.venv/
COPY --chown=atlas:atlas pyproject.toml README.md LICENSE ./
COPY --chown=atlas:atlas packages/ ./packages/
COPY --chown=atlas:atlas apps/ ./apps/
COPY --chown=atlas:atlas config/ ./config/

# Pre-created so a named volume mounted here inherits non-root ownership.
RUN mkdir -p /app/data && chown atlas:atlas /app/data

USER atlas

# ATLAS_ENV defaults to production on purpose: an unconfigured container must
# fail its own invariant checks rather than start in a permissive mode.
ENTRYPOINT ["python", "-m", "atlas.apps.core"]
