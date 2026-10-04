# Shared multi-arch (linux/arm64, linux/amd64) base image for every Python service.
# Build:  docker build -f docker/python.Dockerfile --build-arg SERVICE_PATH=services/app_api .
# SERVICE_PATH is the workspace member to install; the default is the shared core package.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ARG SERVICE_PATH=packages/r2r_core

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1

WORKDIR /app
COPY packages/ packages/
COPY services/ services/
COPY tools/ tools/

# Install the shared core first, then the requested member (a no-op when they are the same).
RUN uv pip install ./packages/r2r_core \
    && if [ "$SERVICE_PATH" != "packages/r2r_core" ]; then uv pip install "./$SERVICE_PATH"; fi
