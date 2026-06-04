# Reference multi-stage Dockerfile for the Python service template.
# Build this from the service directory:
#   docker build --target test .
#   docker build --target runtime -t user:test .
#
# CDP product Cedar overrides are copied at build time from a published policy bundle
# (same pattern as capabilities + cdp-ui-policies). CDP publishes the bundle only;
# this service owns the runtime image.

# cedarpy 4.8.1 needs the glibc manylinux wheel for attribute-based policy evaluation.
ARG PYTHON_IMAGE=python:3.14-slim@sha256:c845af9399020c7e562969a13689e929074a10fd057acd1b1fad06a2fb068e97
ARG CDP_USER_POLICIES_IMAGE=ghcr.io/neosofia/cdp-user-policies:v0.1.0
FROM ${CDP_USER_POLICIES_IMAGE} AS cdp_user_policies

# SQL audit templates (same pattern as authentication)
FROM ghcr.io/neosofia/sql-template:v0.6.0 AS audit-templates

FROM ${PYTHON_IMAGE} AS build-base

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./pyproject.toml
COPY uv.lock ./uv.lock

FROM build-base AS prod-deps
RUN uv sync --frozen --no-dev --no-editable --no-install-project

FROM build-base AS test-deps
RUN uv sync --frozen --all-groups --no-editable --no-install-project

FROM test-deps AS test

COPY alembic.ini ./alembic.ini
COPY src ./src
COPY tests ./tests
COPY roles ./roles
COPY policies ./policies
COPY --from=cdp_user_policies /policies/ ./policies/
COPY openapi.json ./openapi.json

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app"

RUN python -m pytest -q

FROM ${PYTHON_IMAGE} AS runtime
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app \
    && useradd --system --gid app --create-home --home-dir /home/app app

WORKDIR /app

COPY --from=prod-deps /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

COPY alembic.ini ./alembic.ini
COPY src ./src
COPY roles ./roles
COPY policies ./policies
COPY --from=cdp_user_policies /policies/ ./policies/
COPY openapi.json ./openapi.json

# Audit SQL applied by Alembic migration 000
COPY --from=audit-templates /sql/audit /app/audit-templates

EXPOSE 8018

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; port = os.environ.get('PORT', '8018'); urllib.request.urlopen(f'http://localhost:{port}/health', timeout=3)" || exit 1

USER app

CMD ["/bin/sh", "-c", "python -m gunicorn -c src/gunicorn.py src.app:app"]
